from __future__ import annotations

from app.database import ChatMessageResp
from app.database.chat import ChatChannel, ChatMessage, MessageType
from app.database.lazer_user import User
from app.dependencies.database import get_db
from app.dependencies.param import BodyOrForm
from app.dependencies.user import get_current_user
from app.router.v2 import api_v2_router as router

from .server import server

from fastapi import Depends, HTTPException, Query, Security
from pydantic import BaseModel
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession


@router.post("/chat/ack")
async def keep_alive(
    history_since: int | None = Query(None),
    since: int | None = Query(None),
    current_user: User = Security(get_current_user, scopes=["chat.read"]),
    session: AsyncSession = Depends(get_db),
):
    return {"silences": []}


class MessageReq(BaseModel):
    message: str
    is_action: bool = False
    uuid: str | None = None


@router.post("/chat/channels/{channel}/messages", response_model=ChatMessageResp)
async def send_message(
    channel: str,
    req: MessageReq = Depends(BodyOrForm(MessageReq)),
    current_user: User = Security(get_current_user, scopes=["chat.write"]),
    session: AsyncSession = Depends(get_db),
):
    db_channel = await ChatChannel.get(channel, session)
    if db_channel is None:
        raise HTTPException(status_code=404, detail="Channel not found")
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
    resp = await ChatMessageResp.from_db(msg, session, current_user)
    await server.send_message_to_channel(resp)
    return resp


@router.get("/chat/channels/{channel}/messages", response_model=list[ChatMessageResp])
async def get_message(
    channel: str,
    limit: int = Query(50, ge=1, le=50),
    since: int = Query(default=0, ge=0),
    until: int | None = Query(None),
    current_user: User = Security(get_current_user, scopes=["chat.read"]),
    session: AsyncSession = Depends(get_db),
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


@router.put("/chat/channels/{channel}/mark-as-read/{message}", status_code=204)
async def mark_as_read(
    channel: str,
    message: int,
    current_user: User = Security(get_current_user, scopes=["chat.read"]),
    session: AsyncSession = Depends(get_db),
):
    db_channel = await ChatChannel.get(channel, session)
    if db_channel is None:
        raise HTTPException(status_code=404, detail="Channel not found")
    await server.mark_as_read(db_channel.channel_id, message)
