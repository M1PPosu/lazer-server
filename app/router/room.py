from __future__ import annotations

from app.database.room import RoomIndex
from app.dependencies.database import get_db, get_redis
from app.models.room import (
    MultiplayerRoom,
    MultiplayerRoomUser,
    Room,
)

from .api_router import router

from fastapi import Depends, HTTPException, Query
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession


@router.get("/rooms", tags=["rooms"], response_model=list[Room])
async def get_all_rooms(
    mode: str = Query(
        None
    ),  # TODO: lazer源码显示房间不会是除了open以外的其他状态，先放在这里
    status: str = Query(None),
    category: str = Query(None),
    db: AsyncSession = Depends(get_db),
):
    all_room_ids = (await db.exec(select(RoomIndex).where(True))).all()
    redis = get_redis()
    roomsList: list[Room] = []
    if redis:
        for room_index in all_room_ids:
            dumped_room = redis.get(str(room_index.id))
            if dumped_room:
                actual_room = MultiplayerRoom.model_validate_json(str(dumped_room))
                actual_room = Room.from_MultiplayerRoom(actual_room)
                if actual_room.status == status and actual_room.category == category:
                    roomsList.append(actual_room)
        return roomsList
    else:
        raise HTTPException(status_code=500, detail="Redis Error")


@router.put("/rooms/{room}/users/{user}", tags=["rooms"], response_model=Room)
async def add_user_to_room(
    room: int, user: int, password: str, db: AsyncSession = Depends(dependency=get_db)
):
    redis = get_redis()
    if redis:
        dumped_room = redis.get(str(room))
        if not dumped_room:
            raise HTTPException(status_code=404, detail="房间不存在")
        actual_room = MultiplayerRoom.model_validate_json(str(dumped_room))

        # 验证密码
        if password != actual_room.settings.password:
            raise HTTPException(status_code=403, detail="Invalid password")

        # 继续处理加入房间的逻辑
        actual_room.users.append(
            MultiplayerRoomUser(
                id=user, matchState=None, rulesetId=None, beatmapId=None
            )
        )
        actual_room = Room.from_MultiplayerRoom(actual_room)
        return actual_room
    else:
        raise HTTPException(status_code=500, detail="Redis Error")
