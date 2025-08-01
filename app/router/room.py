from __future__ import annotations

from app.database.room import RoomIndex
from app.dependencies.database import get_db, get_redis
from app.dependencies.fetcher import get_fetcher
from app.fetcher import Fetcher
from app.models.room import MultiplayerRoom, MultiplayerRoomState, Room

from .api_router import router

from fastapi import Depends, HTTPException, Query
from redis.asyncio import Redis
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession


@router.get("/rooms", tags=["rooms"], response_model=list[Room])
async def get_all_rooms(
    mode: str | None = Query(None),  # TODO: 对房间根据状态进行筛选
    status: str | None = Query(None),
    category: str | None = Query(
        None
    ),  # TODO: 对房间根据分类进行筛选（真的有人用这功能吗）
    db: AsyncSession = Depends(get_db),
    fetcher: Fetcher = Depends(get_fetcher),
    redis: Redis = Depends(get_redis),
):
    all_roomID = (await db.exec(select(RoomIndex))).all()
    redis = get_redis()
    if redis is not None:
        resp: list[Room] = []
        for id in all_roomID:
            dumped_room = redis.get(str(id))
            validated_room = MultiplayerRoom.model_validate_json(str(dumped_room))
            flag: bool = False
            if status is not None:
                if (
                    validated_room.State == MultiplayerRoomState.OPEN
                    and status == "idle"
                ):
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


class APICreatedRoom(Room):
    error: str | None


@router.post("/rooms", tags=["beatmap"], response_model=APICreatedRoom)
async def create_room(
    room: Room,
    db: AsyncSession = Depends(get_db),
    fetcher: Fetcher = Depends(get_fetcher),
):
    redis = get_redis()
    if redis:
        room_index = RoomIndex()
        db.add(room_index)
        await db.commit()
        await db.refresh(room_index)
        server_room = await MultiplayerRoom.from_apiRoom(room, db, fetcher)
        redis.set(str(room_index.id), server_room.model_dump_json())
        room.room_id = room_index.id
        return APICreatedRoom(**room.model_dump(), error=None)
    else:
        raise HTTPException(status_code=500, detail="redis error")


@router.delete("/rooms/{room}", tags=["room"])
async def remove_room(room: int, db: AsyncSession = Depends(get_db)):
    redis = get_redis()
    if redis:
        redis.delete(str(room))
    room_index = await db.get(RoomIndex, room)
    if room_index:
        await db.delete(room_index)
        await db.commit()
