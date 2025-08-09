from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal

from app.database.beatmap import Beatmap, BeatmapResp
from app.database.beatmapset import BeatmapsetResp
from app.database.lazer_user import User, UserResp
from app.database.multiplayer_event import MultiplayerEvent, MultiplayerEventResp
from app.database.playlist_attempts import ItemAttemptsCount, ItemAttemptsResp
from app.database.playlists import Playlist, PlaylistResp
from app.database.room import Room, RoomBase, RoomResp
from app.database.score import Score
from app.dependencies.database import get_db, get_redis
from app.dependencies.fetcher import get_fetcher
from app.dependencies.user import get_current_user
from app.fetcher import Fetcher
from app.models.room import RoomStatus
from app.signalr.hub import MultiplayerHubs

from .api_router import router

from fastapi import Depends, HTTPException, Query
from pydantic import BaseModel, Field
from redis.asyncio import Redis
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession


@router.get("/rooms", tags=["rooms"], response_model=list[RoomResp])
async def get_all_rooms(
    mode: Literal["open", "ended", "participated", "owned", None] = Query(
        default="open"
    ),  # TODO: 对房间根据状态进行筛选
    category: str | None = Query(None),  # TODO
    status: RoomStatus | None = Query(None),
    db: AsyncSession = Depends(get_db),
    fetcher: Fetcher = Depends(get_fetcher),
    redis: Redis = Depends(get_redis),
    current_user: User = Depends(get_current_user),
):
    resp_list: list[RoomResp] = []
    db_rooms = (await db.exec(select(Room).where(True))).unique().all()
    for room in db_rooms:
        if category == "realtime":
            if room.id in MultiplayerHubs.rooms:
                resp_list.append(await RoomResp.from_db(room))
        elif category is not None:
            if category == room.category:
                resp_list.append(await RoomResp.from_db(room))
        else:
            if room.id not in MultiplayerHubs.rooms:
                resp_list.append(await RoomResp.from_db(room))
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
    db_room.starts_at = datetime.now(UTC)
    db_room.ends_at = db_room.starts_at + timedelta(
        minutes=db_room.duration if db_room.duration is not None else 0
    )
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
    await db.refresh(db_room)
    created_room = APICreatedRoom.model_validate(await RoomResp.from_db(db_room))
    created_room.error = ""
    return created_room


@router.get("/rooms/{room}", tags=["room"], response_model=RoomResp)
async def get_room(
    room: int,
    category: str = Query(default=""),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    redis: Redis = Depends(get_redis),
):
    # 直接从db获取信息，毕竟都一样
    db_room = (await db.exec(select(Room).where(Room.id == room))).first()
    if db_room is None:
        raise HTTPException(404, "Room not found")
    resp = await RoomResp.from_db(
        db_room, include=["current_user_score"], session=db, user=current_user
    )
    return resp


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
    db_room = (await db.exec(select(Room).where(Room.id == room))).first()
    if db_room is not None:
        db_room.participant_count += 1
        await db.commit()
        await db.refresh(db_room)
        resp = await RoomResp.from_db(db_room)
        await db.refresh(db_room)
        for item in db_room.playlist:
            resp.playlist.append(await PlaylistResp.from_db(item, ["beatmap"]))
        return resp
    else:
        raise HTTPException(404, "room not found0")


@router.delete("/rooms/{room}/users/{user}", tags=["room"])
async def remove_user_from_room(
    room: int, user: int, db: AsyncSession = Depends(get_db)
):
    db_room = (await db.exec(select(Room).where(Room.id == room))).first()
    if db_room is not None:
        db_room.participant_count -= 1
        await db.commit()
        return None
    else:
        raise HTTPException(404, "Room not found")


class APILeaderboard(BaseModel):
    leaderboard: list[ItemAttemptsResp] = Field(default_factory=list)
    user_score: ItemAttemptsResp | None = None


@router.get("/rooms/{room}/leaderboard", tags=["room"], response_model=APILeaderboard)
async def get_room_leaderboard(
    room: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_room = (await db.exec(select(Room).where(Room.id == room))).first()
    if db_room is None:
        raise HTTPException(404, "Room not found")

    aggs = await db.exec(
        select(ItemAttemptsCount)
        .where(ItemAttemptsCount.room_id == room)
        .order_by(col(ItemAttemptsCount.total_score).desc())
    )
    aggs_resp = []
    user_agg = None
    for i, agg in enumerate(aggs):
        resp = await ItemAttemptsResp.from_db(agg, db)
        resp.position = i + 1
        # resp.accuracy *= 100
        aggs_resp.append(resp)
        if agg.user_id == current_user.id:
            user_agg = resp
    return APILeaderboard(
        leaderboard=aggs_resp,
        user_score=user_agg,
    )


class RoomEvents(BaseModel):
    beatmaps: list[BeatmapResp] = Field(default_factory=list)
    beatmapsets: dict[int, BeatmapsetResp] = Field(default_factory=dict)
    current_playlist_item_id: int = 0
    events: list[MultiplayerEventResp] = Field(default_factory=list)
    first_event_id: int = 0
    last_event_id: int = 0
    playlist_items: list[PlaylistResp] = Field(default_factory=list)
    room: RoomResp
    user: list[UserResp] = Field(default_factory=list)


@router.get("/rooms/{room_id}/events", response_model=RoomEvents, tags=["room"])
async def get_room_events(
    room_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(100, ge=1, le=1000),
    after: int | None = Query(None, ge=0),
    before: int | None = Query(None, ge=0),
):
    events = (
        await db.exec(
            select(MultiplayerEvent)
            .where(
                MultiplayerEvent.room_id == room_id,
                col(MultiplayerEvent.id) > after if after is not None else True,
                col(MultiplayerEvent.id) < before if before is not None else True,
            )
            .order_by(col(MultiplayerEvent.id).desc())
            .limit(limit)
        )
    ).all()

    user_ids = set()
    playlist_items = {}
    beatmap_ids = set()

    event_resps = []
    first_event_id = 0
    last_event_id = 0

    current_playlist_item_id = 0
    for event in events:
        event_resps.append(MultiplayerEventResp.from_db(event))

        if event.user_id:
            user_ids.add(event.user_id)

        if event.playlist_item_id is not None and (
            playitem := (
                await db.exec(
                    select(Playlist).where(
                        Playlist.id == event.playlist_item_id,
                        Playlist.room_id == room_id,
                    )
                )
            ).first()
        ):
            current_playlist_item_id = playitem.id
            playlist_items[event.playlist_item_id] = playitem
            beatmap_ids.add(playitem.beatmap_id)
            scores = await db.exec(
                select(Score).where(
                    Score.playlist_item_id == event.playlist_item_id,
                    Score.room_id == room_id,
                )
            )
            for score in scores:
                user_ids.add(score.user_id)
                beatmap_ids.add(score.beatmap_id)

        assert event.id is not None
        first_event_id = min(first_event_id, event.id)
        last_event_id = max(last_event_id, event.id)

    if room := MultiplayerHubs.rooms.get(room_id):
        current_playlist_item_id = room.queue.current_item.id
        room_resp = await RoomResp.from_hub(room)
    else:
        room = (await db.exec(select(Room).where(Room.id == room_id))).first()
        if room is None:
            raise HTTPException(404, "Room not found")
        room_resp = await RoomResp.from_db(room)

    users = await db.exec(select(User).where(col(User.id).in_(user_ids)))
    user_resps = [await UserResp.from_db(user, db) for user in users]
    beatmaps = await db.exec(select(Beatmap).where(col(Beatmap.id).in_(beatmap_ids)))
    beatmap_resps = [
        await BeatmapResp.from_db(beatmap, session=db) for beatmap in beatmaps
    ]
    beatmapset_resps = {}
    for beatmap_resp in beatmap_resps:
        beatmapset_resps[beatmap_resp.beatmapset_id] = beatmap_resp.beatmapset

    playlist_items_resps = [
        await PlaylistResp.from_db(item) for item in playlist_items.values()
    ]

    return RoomEvents(
        beatmaps=beatmap_resps,
        beatmapsets=beatmapset_resps,
        current_playlist_item_id=current_playlist_item_id,
        events=event_resps,
        first_event_id=first_event_id,
        last_event_id=last_event_id,
        playlist_items=playlist_items_resps,
        room=room_resp,
        user=user_resps,
    )
