from __future__ import annotations

from app.database.room import RoomIndex
from app.dependencies.database import get_db, get_redis
from app.dependencies.fetcher import get_fetcher
from app.fetcher import Fetcher
from app.models.room import MultiplayerRoom, MultiplayerRoomState, Room

from api_router import router
from fastapi import Depends, HTTPException, Query
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession


@router.get("/rooms", tags=["rooms"], response_model=list[Room])
async def get_all_rooms(
    mode: str = Query(None),  # TODO: 对房间根据状态进行筛选
    status: str = Query(None),
    category: str = Query(None),  # TODO: 对房间根据分类进行筛选（真的有人用这功能吗）
    db: AsyncSession = Depends(get_db),
    fetcher: Fetcher = Depends(get_fetcher),
):
    all_roomID = (await db.exec(select(RoomIndex))).all()
    redis = get_redis()
    if redis is not None:
        resp: list[Room] = []
        for id in all_roomID:
            dumped_room = redis.get(str(id))
            validated_room = MultiplayerRoom.model_validate_json(str(dumped_room))
            flag: bool = False
            if validated_room.State == MultiplayerRoomState.OPEN and status == "idle":
                flag = True
            elif validated_room != MultiplayerRoomState.CLOSED:
                flag = True
            if flag:
                resp.append(
                    await Room.from_mpRoom(
                        MultiplayerRoom.model_validate_json(str(dumped_room)),
                        db,
                        fetcher,
                    )
                )
        return resp
    else:
        raise HTTPException(status_code=500, detail="Redis Error")


@router.get("/rooms/{room}", tags=["room"], response_model=Room)
async def get_room(
    room: int,
    db: AsyncSession = Depends(get_db),
    fetcher: Fetcher = Depends(get_fetcher),
):
    redis = get_redis()
    if redis:
        dumped_room = str(redis.get(str(room)))
        if dumped_room is not None:
            resp = await Room.from_mpRoom(
                MultiplayerRoom.model_validate_json(str(dumped_room)), db, fetcher
            )
            return resp
        else:
            raise HTTPException(status_code=404, detail="Room Not Found")
    else:
        raise HTTPException(status_code=500, detail="Redis error")
