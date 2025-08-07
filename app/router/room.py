from __future__ import annotations

from datetime import UTC, datetime
from time import timezone
from typing import Literal

from app.database.lazer_user import User
from app.database.playlists import Playlist, PlaylistResp
from app.database.room import Room, RoomBase, RoomResp
from app.dependencies.database import get_db, get_redis
from app.dependencies.fetcher import get_fetcher
from app.dependencies.user import get_current_user
from app.fetcher import Fetcher
from app.models.multiplayer_hub import (
    MultiplayerRoom,
    MultiplayerRoomUser,
    ServerMultiplayerRoom,
)
from app.models.room import RoomStatus
from app.signalr.hub import MultiplayerHubs

from .api_router import router

from fastapi import Depends, HTTPException, Query
from redis.asyncio import Redis
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.status import HTTP_417_EXPECTATION_FAILED


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
        # if category == "realtime" and room.category != "normal":
        #     continue
        # elif category != room.category and category != "":
        #     continue
        resp_list.append(await RoomResp.from_hub(room))
    return resp_list


class APICreatedRoom(RoomResp):
    error: str = ""


class APIUploadedRoom(RoomBase):
    def to_room(self) -> Room:
        """
        将 APIUploadedRoom 转换为 Room 对象，playlist 字段需单独处理。
        """
        room_dict = self.model_dump()
        room_dict.pop("playlist", None)
        # host_id 已在字段中
        return Room(**room_dict)

    id: int | None
    host_id: int | None = None
    playlist: list[Playlist]


@router.post("/rooms", tags=["room"], response_model=APICreatedRoom)
async def create_room(
    room: APIUploadedRoom,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # db_room = Room.from_resp(room)
    await db.refresh(current_user)
    user_id = current_user.id
    db_room = room.to_room()
    db_room.host_id = current_user.id if current_user.id else 1
    db.add(db_room)
    await db.commit()
    await db.refresh(db_room)

    playlist: list[Playlist] = []
    # 处理 APIUploadedRoom 里的 playlist 字段
    for item in room.playlist:
        # 确保 room_id 正确赋值
        item.id = await Playlist.get_next_id_for_room(db_room.id, db)
        item.room_id = db_room.id
        item.owner_id = user_id if user_id else 1
        db.add(item)
        await db.commit()
        await db.refresh(item)
        playlist.append(item)
        await db.refresh(db_room)
    db_room.playlist = playlist
    server_room = ServerMultiplayerRoom(
        room=MultiplayerRoom.from_db(db_room),
        category=db_room.category,
        start_at=datetime.now(UTC),
        hub=MultiplayerHubs,
    )
    MultiplayerHubs.rooms[db_room.id] = server_room
    created_room = APICreatedRoom.model_validate(await RoomResp.from_db(db_room))
    created_room.error = ""
    return created_room


@router.get("/rooms/{room}", tags=["room"], response_model=RoomResp)
async def get_room(
    room: int,
    db: AsyncSession = Depends(get_db),
):
    server_room = MultiplayerHubs.rooms[room]
    return await RoomResp.from_hub(server_room)


@router.delete("/rooms/{room}", tags=["room"])
async def delete_room(room: int, db: AsyncSession = Depends(get_db)):
    db_room = (await db.exec(select(Room).where(Room.id == room))).first()
    if db_room is None:
        raise HTTPException(404, "Room not found")
    else:
        await db.delete(db_room)
        return None


@router.put("/rooms/{room}/users/{user}", tags=["room"])
async def add_user_to_room(room: int, user: int, db: AsyncSession = Depends(get_db)):
    server_room = MultiplayerHubs.rooms[room]
    server_room.room.users.append(MultiplayerRoomUser(user_id=user))
    db_room = (await db.exec(select(Room).where(Room.id == room))).first()
    if db_room is not None:
        db_room.participant_count += 1
        await db.commit()
        resp = await RoomResp.from_hub(server_room)
        await db.refresh(db_room)
        for item in db_room.playlist:
            resp.playlist.append(await PlaylistResp.from_db(item))
        return resp
    else:
        raise HTTPException(404, "room not found0")
