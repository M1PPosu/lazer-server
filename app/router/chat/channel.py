from __future__ import annotations

from typing import Any

from app.database.chat import (
    ChannelType,
    ChatChannel,
    ChatChannelResp,
)
from app.database.lazer_user import User, UserResp
from app.dependencies.database import get_db, get_redis
from app.dependencies.user import get_current_user
from app.router.v2 import api_v2_router as router

from .server import server

from fastapi import Depends, HTTPException, Query, Security
from pydantic import BaseModel, Field
from redis.asyncio import Redis
from sqlmodel import select
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
        channel_ids = server.get_user_joined_channel(current_user.id)
        for channel_id in channel_ids:
            channel = await ChatChannel.get(channel_id, session)
            if channel:
                resp.presence.append(
                    await ChatChannelResp.from_db(
                        channel,
                        session,
                        server.channels.get(channel_id, []),
                        current_user,
                        redis,
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
                server.channels.get(channel.channel_id, []),
                current_user,
                redis,
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
    return GetChannelResp(
        channel=await ChatChannelResp.from_db(
            db_channel,
            session,
            server.channels.get(db_channel.channel_id, []),
            current_user,
            redis,
        )
    )
