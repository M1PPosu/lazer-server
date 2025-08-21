from __future__ import annotations

from app.database import ChatMessageResp
from app.database.chat import (
    ChannelType,
    ChatChannel,
    ChatChannelResp,
    ChatMessage,
    MessageType,
    SilenceUser,
    UserSilenceResp,
)
from app.database.lazer_user import User
from app.dependencies.database import Database, get_redis
from app.dependencies.param import BodyOrForm
from app.dependencies.user import get_current_user
from app.models.notification import ChannelMessage, ChannelMessageTeam
from app.router.v2 import api_v2_router as router

from .banchobot import bot
from .server import server

from fastapi import Depends, HTTPException, Path, Query, Security
from pydantic import BaseModel, Field
from redis.asyncio import Redis
from sqlmodel import col, select


class KeepAliveResp(BaseModel):
    silences: list[UserSilenceResp] = Field(default_factory=list)


@router.post(
    "/chat/ack",
    name="保持连接",
    response_model=KeepAliveResp,
    description="保持公共频道的连接。同时返回最近的禁言列表。",
    tags=["聊天"],
)
async def keep_alive(
    session: Database,
    history_since: int | None = Query(
        None, description="获取自此禁言 ID 之后的禁言记录"
    ),
    since: int | None = Query(None, description="获取自此消息 ID 之后的禁言记录"),
    current_user: User = Security(get_current_user, scopes=["chat.read"]),
):
    resp = KeepAliveResp()
    if history_since:
        silences = (
            await session.exec(
                select(SilenceUser).where(col(SilenceUser.id) > history_since)
            )
        ).all()
        resp.silences.extend([UserSilenceResp.from_db(silence) for silence in silences])
    elif since:
        msg = await session.get(ChatMessage, since)
        if msg:
            silences = (
                await session.exec(
                    select(SilenceUser).where(
                        col(SilenceUser.banned_at) > msg.timestamp
                    )
                )
            ).all()
            resp.silences.extend(
                [UserSilenceResp.from_db(silence) for silence in silences]
            )

    return resp


class MessageReq(BaseModel):
    message: str
    is_action: bool = False
    uuid: str | None = None


@router.post(
    "/chat/channels/{channel}/messages",
    response_model=ChatMessageResp,
    name="发送消息",
    description="发送消息到指定频道。",
    tags=["聊天"],
)
async def send_message(
    session: Database,
    channel: str = Path(..., description="频道 ID/名称"),
    req: MessageReq = Depends(BodyOrForm(MessageReq)),
    current_user: User = Security(get_current_user, scopes=["chat.write"]),
):
    db_channel = await ChatChannel.get(channel, session)
    if db_channel is None:
        raise HTTPException(status_code=404, detail="Channel not found")

    assert db_channel.channel_id
    assert current_user.id
    msg = ChatMessage(
        channel_id=db_channel.channel_id,
        content=req.message,
        sender_id=current_user.id,
        type=MessageType.ACTION if req.is_action else MessageType.PLAIN,
        uuid=req.uuid,
    )
    session.add(msg)
    await session.commit()
    await session.refresh(msg)
    await session.refresh(current_user)
    await session.refresh(db_channel)
    resp = await ChatMessageResp.from_db(msg, session, current_user)
    is_bot_command = req.message.startswith("!")
    await server.send_message_to_channel(
        resp, is_bot_command and db_channel.type == ChannelType.PUBLIC
    )
    if is_bot_command:
        await bot.try_handle(current_user, db_channel, req.message, session)
    if db_channel.type == ChannelType.PM:
        user_ids = db_channel.name.split("_")[1:]
        await server.new_private_notification(
            ChannelMessage(
                msg, current_user, [int(u) for u in user_ids], db_channel.type
            )
        )
    elif db_channel.type == ChannelType.TEAM:
        await server.new_private_notification(ChannelMessageTeam(msg, current_user))
    return resp


@router.get(
    "/chat/channels/{channel}/messages",
    response_model=list[ChatMessageResp],
    name="获取消息",
    description="获取指定频道的消息列表。",
    tags=["聊天"],
)
async def get_message(
    session: Database,
    channel: str,
    limit: int = Query(50, ge=1, le=50, description="获取消息的数量"),
    since: int = Query(default=0, ge=0, description="获取自此消息 ID 之后的消息记录"),
    until: int | None = Query(None, description="获取自此消息 ID 之前的消息记录"),
    current_user: User = Security(get_current_user, scopes=["chat.read"]),
):
    db_channel = await ChatChannel.get(channel, session)
    if db_channel is None:
        raise HTTPException(status_code=404, detail="Channel not found")
    messages = await session.exec(
        select(ChatMessage)
        .where(
            ChatMessage.channel_id == db_channel.channel_id,
            col(ChatMessage.message_id) > since,
            col(ChatMessage.message_id) < until if until is not None else True,
        )
        .order_by(col(ChatMessage.timestamp).desc())
        .limit(limit)
    )
    resp = [await ChatMessageResp.from_db(msg, session) for msg in messages]
    resp.reverse()
    return resp


@router.put(
    "/chat/channels/{channel}/mark-as-read/{message}",
    status_code=204,
    name="标记消息为已读",
    description="标记指定消息为已读。",
    tags=["聊天"],
)
async def mark_as_read(
    session: Database,
    channel: str = Path(..., description="频道 ID/名称"),
    message: int = Path(..., description="消息 ID"),
    current_user: User = Security(get_current_user, scopes=["chat.read"]),
):
    db_channel = await ChatChannel.get(channel, session)
    if db_channel is None:
        raise HTTPException(status_code=404, detail="Channel not found")
    assert db_channel.channel_id
    assert current_user.id
    await server.mark_as_read(db_channel.channel_id, current_user.id, message)


class PMReq(BaseModel):
    target_id: int
    message: str
    is_action: bool = False
    uuid: str | None = None


class NewPMResp(BaseModel):
    channel: ChatChannelResp
    message: ChatMessageResp
    new_channel_id: int


@router.post(
    "/chat/new",
    name="创建私聊频道",
    description="创建一个新的私聊频道。",
    tags=["聊天"],
)
async def create_new_pm(
    session: Database,
    req: PMReq = Depends(BodyOrForm(PMReq)),
    current_user: User = Security(get_current_user, scopes=["chat.write"]),
    redis: Redis = Depends(get_redis),
):
    user_id = current_user.id
    target = await session.get(User, req.target_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Target user not found")
    is_can_pm, block = await target.is_user_can_pm(current_user, session)
    if not is_can_pm:
        raise HTTPException(status_code=403, detail=block)

    assert user_id
    channel = await ChatChannel.get_pm_channel(user_id, req.target_id, session)
    if channel is None:
        channel = ChatChannel(
            name=f"pm_{user_id}_{req.target_id}",
            description="Private message channel",
            type=ChannelType.PM,
        )
        session.add(channel)
        await session.commit()
        await session.refresh(channel)
        await session.refresh(target)
        await session.refresh(current_user)

    assert channel.channel_id
    await server.batch_join_channel([target, current_user], channel, session)
    channel_resp = await ChatChannelResp.from_db(
        channel, session, current_user, redis, server.channels[channel.channel_id]
    )
    msg = ChatMessage(
        channel_id=channel.channel_id,
        content=req.message,
        sender_id=user_id,
        type=MessageType.ACTION if req.is_action else MessageType.PLAIN,
        uuid=req.uuid,
    )
    session.add(msg)
    await session.commit()
    await session.refresh(msg)
    await session.refresh(current_user)
    await session.refresh(channel)
    message_resp = await ChatMessageResp.from_db(msg, session, current_user)
    await server.send_message_to_channel(message_resp)
    return NewPMResp(
        channel=channel_resp,
        message=message_resp,
        new_channel_id=channel_resp.channel_id,
    )
