from __future__ import annotations

from typing import Any, Literal, Self

from app.database.chat import (
    ChannelType,
    ChatChannel,
    ChatChannelResp,
)
from app.database.lazer_user import User, UserResp
from app.dependencies.database import get_db, get_redis
from app.dependencies.param import BodyOrForm
from app.dependencies.user import get_current_user
from app.router.v2 import api_v2_router as router

from .server import server

from fastapi import Depends, HTTPException, Query, Security
from pydantic import BaseModel, Field, model_validator
from redis.asyncio import Redis
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession


class UpdateResponse(BaseModel):
    presence: list[ChatChannelResp] = Field(default_factory=list)
    silences: list[Any] = Field(default_factory=list)


@router.get("/chat/updates", response_model=UpdateResponse)
async def get_update(
    history_since: int | None = Query(None),
    since: int | None = Query(None),
    current_user: User = Security(get_current_user, scopes=["chat.read"]),
    session: AsyncSession = Depends(get_db),
    includes: list[str] = Query(["presence"], alias="includes[]"),
    redis: Redis = Depends(get_redis),
):
    resp = UpdateResponse()
    if "presence" in includes:
        assert current_user.id
        channel_ids = server.get_user_joined_channel(current_user.id)
        for channel_id in channel_ids:
            channel = await ChatChannel.get(channel_id, session)
            if channel:
                resp.presence.append(
                    await ChatChannelResp.from_db(
                        channel,
                        session,
                        current_user,
                        redis,
                        server.channels.get(channel_id, [])
                        if channel.type != ChannelType.PUBLIC
                        else None,
                    )
                )
    return resp


@router.put("/chat/channels/{channel}/users/{user}", response_model=ChatChannelResp)
async def join_channel(
    channel: str,
    user: str,
    current_user: User = Security(get_current_user, scopes=["chat.write_manage"]),
    session: AsyncSession = Depends(get_db),
):
    db_channel = await ChatChannel.get(channel, session)

    if db_channel is None:
        raise HTTPException(status_code=404, detail="Channel not found")
    return await server.join_channel(current_user, db_channel, session)


@router.delete(
    "/chat/channels/{channel}/users/{user}",
    status_code=204,
)
async def leave_channel(
    channel: str,
    user: str,
    current_user: User = Security(get_current_user, scopes=["chat.write_manage"]),
    session: AsyncSession = Depends(get_db),
):
    db_channel = await ChatChannel.get(channel, session)

    if db_channel is None:
        raise HTTPException(status_code=404, detail="Channel not found")
    await server.leave_channel(current_user, db_channel, session)
    return


@router.get("/chat/channels")
async def get_channel_list(
    current_user: User = Security(get_current_user, scopes=["chat.read"]),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    channels = (
        await session.exec(
            select(ChatChannel).where(ChatChannel.type == ChannelType.PUBLIC)
        )
    ).all()
    results = []
    for channel in channels:
        assert channel.channel_id is not None
        results.append(
            await ChatChannelResp.from_db(
                channel,
                session,
                current_user,
                redis,
                server.channels.get(channel.channel_id, [])
                if channel.type != ChannelType.PUBLIC
                else None,
            )
        )
    return results


class GetChannelResp(BaseModel):
    channel: ChatChannelResp
    users: list[UserResp] = Field(default_factory=list)


@router.get("/chat/channels/{channel}")
async def get_channel(
    channel: str,
    current_user: User = Security(get_current_user, scopes=["chat.read"]),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    db_channel = await ChatChannel.get(channel, session)
    if db_channel is None:
        raise HTTPException(status_code=404, detail="Channel not found")
    assert db_channel.channel_id is not None

    users = []
    if db_channel.type == ChannelType.PM:
        user_ids = db_channel.name.split("_")[1:]
        if len(user_ids) != 2:
            raise HTTPException(status_code=404, detail="Target user not found")
        for id_ in user_ids:
            if int(id_) == current_user.id:
                continue
            target_user = await session.get(User, int(id_))
            if target_user is None:
                raise HTTPException(status_code=404, detail="Target user not found")
            users.extend([target_user, current_user])
            break

    return GetChannelResp(
        channel=await ChatChannelResp.from_db(
            db_channel,
            session,
            current_user,
            redis,
            server.channels.get(db_channel.channel_id, [])
            if db_channel.type != ChannelType.PUBLIC
            else None,
        )
    )


class CreateChannelReq(BaseModel):
    class AnnounceChannel(BaseModel):
        name: str
        description: str

    message: str | None = None
    type: Literal["ANNOUNCE", "PM"] = "PM"
    target_id: int | None = None
    target_ids: list[int] | None = None
    channel: AnnounceChannel | None = None

    @model_validator(mode="after")
    def check(self) -> Self:
        if self.type == "PM":
            if self.target_id is None:
                raise ValueError("target_id must be set for PM channels")
        else:
            if self.target_ids is None or self.channel is None or self.message is None:
                raise ValueError(
                    "target_ids, channel, and message must be set for ANNOUNCE channels"
                )
        return self


@router.post("/chat/channels")
async def create_channel(
    req: CreateChannelReq = Depends(BodyOrForm(CreateChannelReq)),
    current_user: User = Security(get_current_user, scopes=["chat.write_manage"]),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    if req.type == "PM":
        target = await session.get(User, req.target_id)
        if not target:
            raise HTTPException(status_code=404, detail="Target user not found")
        is_can_pm, block = await target.is_user_can_pm(current_user, session)
        if not is_can_pm:
            raise HTTPException(status_code=403, detail=block)

        channel = await ChatChannel.get_pm_channel(
            current_user.id,  # pyright: ignore[reportArgumentType]
            req.target_id,  # pyright: ignore[reportArgumentType]
            session,
        )
        channel_name = f"pm_{current_user.id}_{req.target_id}"
    else:
        channel_name = req.channel.name if req.channel else "Unnamed Channel"
        channel = await ChatChannel.get(channel_name, session)

    if channel is None:
        channel = ChatChannel(
            name=channel_name,
            description=req.channel.description
            if req.channel
            else "Private message channel",
            type=ChannelType.PM if req.type == "PM" else ChannelType.ANNOUNCE,
        )
        session.add(channel)
        await session.commit()
        await session.refresh(channel)
        await session.refresh(current_user)
    if req.type == "PM":
        await session.refresh(target)  # pyright: ignore[reportPossiblyUnboundVariable]
        await server.batch_join_channel([target, current_user], channel, session)  # pyright: ignore[reportPossiblyUnboundVariable]
    else:
        target_users = await session.exec(
            select(User).where(col(User.id).in_(req.target_ids or []))
        )
        await server.batch_join_channel([*target_users, current_user], channel, session)

    await server.join_channel(current_user, channel, session)
    assert channel.channel_id
    return await ChatChannelResp.from_db(
        channel,
        session,
        current_user,
        redis,
        server.channels.get(channel.channel_id, []),
        include_recent_messages=True,
    )
