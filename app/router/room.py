from __future__ import annotations

from typing import Literal

from app.database.room import RoomResp
from app.dependencies.database import get_db, get_redis
from app.dependencies.fetcher import get_fetcher
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
        None
    ),  # TODO: 对房间根据状态进行筛选
    category: str = Query(default="realtime"),  # TODO
    status: RoomStatus | None = Query(None),
    db: AsyncSession = Depends(get_db),
    fetcher: Fetcher = Depends(get_fetcher),
    redis: Redis = Depends(get_redis),
):
    rooms = MultiplayerHubs.rooms.values()
    return [await RoomResp.from_hub(room) for room in rooms]


# @router.get("/rooms/{room}", tags=["room"], response_model=Room)
# async def get_room(
#     room: int,
#     db: AsyncSession = Depends(get_db),
#     fetcher: Fetcher = Depends(get_fetcher),
# ):
#     redis = get_redis()
#     if redis:
#         dumped_room = str(redis.get(str(room)))
#         if dumped_room is not None:
#             resp = await Room.from_mpRoom(
#                 MultiplayerRoom.model_validate_json(str(dumped_room)), db, fetcher
#             )
#             return resp
#         else:
#             raise HTTPException(status_code=404, detail="Room Not Found")
#     else:
#         raise HTTPException(status_code=500, detail="Redis error")


# class APICreatedRoom(Room):
#     error: str | None


# @router.post("/rooms", tags=["beatmap"], response_model=APICreatedRoom)
# async def create_room(
#     room: Room,
#     db: AsyncSession = Depends(get_db),
#     fetcher: Fetcher = Depends(get_fetcher),
# ):
#     redis = get_redis()
#     if redis:
#         room_index = RoomIndex()
#         db.add(room_index)
#         await db.commit()
#         await db.refresh(room_index)
#         server_room = await MultiplayerRoom.from_apiRoom(room, db, fetcher)
#         redis.set(str(room_index.id), server_room.model_dump_json())
#         room.room_id = room_index.id
#         return APICreatedRoom(**room.model_dump(), error=None)
#     else:
#         raise HTTPException(status_code=500, detail="redis error")


# @router.delete("/rooms/{room}", tags=["room"])
# async def remove_room(room: int, db: AsyncSession = Depends(get_db)):
#     redis = get_redis()
#     if redis:
#         redis.delete(str(room))
#     room_index = await db.get(RoomIndex, room)
#     if room_index:
#         await db.delete(room_index)
#         await db.commit()
