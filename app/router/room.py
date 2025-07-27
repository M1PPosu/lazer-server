from __future__ import annotations

from app.database.room import RoomIndex
from app.dependencies.database import get_db, get_redis
from app.models.room import Room

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
                actual_room = Room.model_validate_json(str(dumped_room))
                if actual_room.status == status and actual_room.category == category:
                    roomsList.append(actual_room)
        return roomsList
    else:
        raise HTTPException(status_code=500, detail="Redis Error")
