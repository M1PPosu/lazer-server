from __future__ import annotations

from typing import Literal

from app.database.lazer_user import User
from app.database.room import RoomResp
from app.dependencies.database import get_db, get_redis
from app.dependencies.fetcher import get_fetcher
from app.dependencies.user import get_current_user
from app.fetcher import Fetcher
from app.models.room import RoomStatus
from app.signalr.hub import MultiplayerHubs

from .api_router import router

from fastapi import Depends, Query
from redis.asyncio import Redis
from sqlmodel.ext.asyncio.session import AsyncSession


@router.get("/rooms", tags=["rooms"], response_model=list[RoomResp])
async def get_all_rooms(
    mode: Literal["open", "ended", "participated", "owned", None] = Query(
        default="open"
    ),  # TODO: 对房间根据状态进行筛选
    category: str = Query(default="realtime"),  # TODO
    status: RoomStatus | None = Query(None),
    db: AsyncSession = Depends(get_db),
    fetcher: Fetcher = Depends(get_fetcher),
    redis: Redis = Depends(get_redis),
    current_user: User = Depends(get_current_user),
):
    rooms = MultiplayerHubs.rooms.values()
    resp_list: list[RoomResp] = []
    for room in rooms:
        if category != "realtime":  # 歌单模式的处理逻辑
            if room.category == category:
                if mode == "owned":
                    if (
                        room.room.host.user_id if room.room.host is not None else 0
                    ) != current_user.id:
                        continue
            else:
                continue
        else:
            if mode == "owned":
                if (
                    room.room.host.user_id if room.room.host is not None else 0
                ) != current_user.id:
                    continue
            if room.status != status:
                continue
        resp_list.append(await RoomResp.from_hub(room))
    return resp_list
