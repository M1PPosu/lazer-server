from __future__ import annotations

from dataclasses import dataclass
import datetime
from typing import TYPE_CHECKING, Annotated, Any, Literal

from app.database.beatmap import Beatmap
from app.dependencies.database import engine
from app.exception import InvokeException

from .room import (
    DownloadState,
    MatchType,
    MultiplayerRoomState,
    MultiplayerUserState,
    QueueMode,
    RoomCategory,
    RoomStatus,
)
from .signalr import (
    EnumByIndex,
    MessagePackArrayModel,
    UserState,
    msgpack_union,
    msgpack_union_dump,
)

from msgpack_lazer_api import APIMod
from pydantic import Field, field_serializer, field_validator
from sqlmodel.ext.asyncio.session import AsyncSession

if TYPE_CHECKING:
    from app.signalr.hub import MultiplayerHub

HOST_LIMIT = 50
PER_USER_LIMIT = 3


class MultiplayerClientState(UserState):
    room_id: int = 0


class MultiplayerRoomSettings(MessagePackArrayModel):
    name: str = "Unnamed Room"
    playlist_item_id: int = 0
    password: str = ""
    match_type: Annotated[MatchType, EnumByIndex(MatchType)] = MatchType.HEAD_TO_HEAD
    queue_mode: Annotated[QueueMode, EnumByIndex(QueueMode)] = QueueMode.HOST_ONLY
    auto_start_duration: int = 0
    auto_skip: bool = False


class BeatmapAvailability(MessagePackArrayModel):
    state: Annotated[DownloadState, EnumByIndex(DownloadState)] = DownloadState.UNKNOWN
    progress: float | None = None


class _MatchUserState(MessagePackArrayModel): ...


class TeamVersusUserState(_MatchUserState):
    team_id: int

    type: Literal[0] = Field(0, exclude=True)


MatchUserState = TeamVersusUserState


class _MatchRoomState(MessagePackArrayModel): ...


class MultiplayerTeam(MessagePackArrayModel):
    id: int
    name: str


class TeamVersusRoomState(_MatchRoomState):
    teams: list[MultiplayerTeam] = Field(
        default_factory=lambda: [
            MultiplayerTeam(id=0, name="Team Red"),
            MultiplayerTeam(id=1, name="Team Blue"),
        ]
    )

    type: Literal[0] = Field(0, exclude=True)


MatchRoomState = TeamVersusRoomState


class PlaylistItem(MessagePackArrayModel):
    id: int
    owner_id: int
    beatmap_id: int
    checksum: str
    ruleset_id: int
    required_mods: list[APIMod] = Field(default_factory=list)
    allowed_mods: list[APIMod] = Field(default_factory=list)
    expired: bool
    order: int
    played_at: datetime.datetime | None = None
    star: float
    freestyle: bool


class _MultiplayerCountdown(MessagePackArrayModel):
    id: int
    remaining: int
    is_exclusive: bool


class MatchStartCountdown(_MultiplayerCountdown):
    type: Literal[0] = Field(0, exclude=True)


class ForceGameplayStartCountdown(_MultiplayerCountdown):
    type: Literal[1] = Field(1, exclude=True)


class ServerShuttingDownCountdown(_MultiplayerCountdown):
    type: Literal[2] = Field(2, exclude=True)


MultiplayerCountdown = (
    MatchStartCountdown | ForceGameplayStartCountdown | ServerShuttingDownCountdown
)


class MultiplayerRoomUser(MessagePackArrayModel):
    user_id: int
    state: Annotated[MultiplayerUserState, EnumByIndex(MultiplayerUserState)] = (
        MultiplayerUserState.IDLE
    )
    availability: BeatmapAvailability = BeatmapAvailability(
        state=DownloadState.UNKNOWN, progress=None
    )
    mods: list[APIMod] = Field(default_factory=list)
    match_state: MatchUserState | None = None
    ruleset_id: int | None = None  # freestyle
    beatmap_id: int | None = None  # freestyle

    @field_validator("match_state", mode="before")
    def union_validate(v: Any):
        if isinstance(v, list):
            return msgpack_union(v)
        return v

    @field_serializer("match_state")
    def union_serialize(v: Any):
        return msgpack_union_dump(v)


class MultiplayerRoom(MessagePackArrayModel):
    room_id: int
    state: Annotated[MultiplayerRoomState, EnumByIndex(MultiplayerRoomState)]
    settings: MultiplayerRoomSettings
    users: list[MultiplayerRoomUser] = Field(default_factory=list)
    host: MultiplayerRoomUser | None = None
    match_state: MatchRoomState | None = None
    playlist: list[PlaylistItem] = Field(default_factory=list)
    active_cooldowns: list[MultiplayerCountdown] = Field(default_factory=list)
    channel_id: int

    @field_validator("match_state", mode="before")
    def union_validate(v: Any):
        if isinstance(v, list):
            return msgpack_union(v)
        return v

    @field_serializer("match_state")
    def union_serialize(v: Any):
        return msgpack_union_dump(v)


class MultiplayerQueue:
    def __init__(self, room: "ServerMultiplayerRoom", hub: "MultiplayerHub"):
        self.server_room = room
        self.hub = hub
        self.current_index = 0

    @property
    def upcoming_items(self):
        return sorted(
            (item for item in self.room.playlist if not item.expired),
            key=lambda i: i.order,
        )

    @property
    def room(self):
        return self.server_room.room

    async def update_order(self):
        from app.database import Playlist

        match self.room.settings.queue_mode:
            case QueueMode.ALL_PLAYERS_ROUND_ROBIN:
                ordered_active_items = []

                is_first_set = True
                first_set_order_by_user_id = {}

                active_items = [item for item in self.room.playlist if not item.expired]
                active_items.sort(key=lambda x: x.id)

                user_item_groups = {}
                for item in active_items:
                    if item.owner_id not in user_item_groups:
                        user_item_groups[item.owner_id] = []
                    user_item_groups[item.owner_id].append(item)

                max_items = max(
                    (len(items) for items in user_item_groups.values()), default=0
                )

                for i in range(max_items):
                    current_set = []
                    for user_id, items in user_item_groups.items():
                        if i < len(items):
                            current_set.append(items[i])

                    if is_first_set:
                        current_set.sort(key=lambda item: (item.order, item.id))
                        ordered_active_items.extend(current_set)
                        first_set_order_by_user_id = {
                            item.owner_id: idx
                            for idx, item in enumerate(ordered_active_items)
                        }
                    else:
                        current_set.sort(
                            key=lambda item: first_set_order_by_user_id.get(
                                item.owner_id, 0
                            )
                        )
                        ordered_active_items.extend(current_set)

                    is_first_set = False

                for idx, item in enumerate(ordered_active_items):
                    item.order = idx
            case _:
                ordered_active_items = sorted(
                    (item for item in self.room.playlist if not item.expired),
                    key=lambda x: x.id,
                )
        async with AsyncSession(engine) as session:
            for idx, item in enumerate(ordered_active_items):
                if item.order == idx:
                    continue
                item.order = idx
                await Playlist.update(item, self.room.room_id, session)
                await self.hub.playlist_changed(
                    self.server_room, item, beatmap_changed=False
                )

    async def update_current_item(self):
        upcoming_items = self.upcoming_items
        next_item = (
            upcoming_items[0]
            if upcoming_items
            else max(
                self.room.playlist,
                key=lambda i: i.played_at or datetime.datetime.min,
            )
        )
        self.current_index = self.room.playlist.index(next_item)
        last_id = self.room.settings.playlist_item_id
        self.room.settings.playlist_item_id = next_item.id
        if last_id != next_item.id:
            await self.hub.setting_changed(self.server_room, True)

    async def add_item(self, item: PlaylistItem, user: MultiplayerRoomUser):
        from app.database import Playlist

        is_host = self.room.host and self.room.host.user_id == user.user_id
        if self.room.settings.queue_mode == QueueMode.HOST_ONLY and not is_host:
            raise InvokeException("You are not the host")

        limit = HOST_LIMIT if is_host else PER_USER_LIMIT
        if (
            len(
                list(
                    filter(
                        lambda x: x.owner_id == user.user_id,
                        self.room.playlist,
                    )
                )
            )
            >= limit
        ):
            raise InvokeException(f"You can only have {limit} items in the queue")

        if item.freestyle and len(item.allowed_mods) > 0:
            raise InvokeException("Freestyle items cannot have allowed mods")

        async with AsyncSession(engine) as session:
            async with session:
                beatmap = await session.get(Beatmap, item.beatmap_id)
                if beatmap is None:
                    raise InvokeException("Beatmap not found")
                if item.checksum != beatmap.checksum:
                    raise InvokeException("Checksum mismatch")
                # TODO: mods validation
                item.owner_id = user.user_id
                item.star = float(
                    beatmap.difficulty_rating
                )  # FIXME: beatmap use decimal
                await Playlist.add_to_db(item, self.room.room_id, session)
                self.room.playlist.append(item)
        await self.hub.playlist_added(self.server_room, item)
        await self.update_order()
        await self.update_current_item()

    async def edit_item(self, item: PlaylistItem, user: MultiplayerRoomUser):
        from app.database import Playlist

        if item.freestyle and len(item.allowed_mods) > 0:
            raise InvokeException("Freestyle items cannot have allowed mods")

        async with AsyncSession(engine) as session:
            async with session:
                beatmap = await session.get(Beatmap, item.beatmap_id)
                if beatmap is None:
                    raise InvokeException("Beatmap not found")
                if item.checksum != beatmap.checksum:
                    raise InvokeException("Checksum mismatch")

                existing_item = next(
                    (i for i in self.room.playlist if i.id == item.id), None
                )
                if existing_item is None:
                    raise InvokeException(
                        "Attempted to change an item that doesn't exist"
                    )

                if existing_item.owner_id != user.user_id and self.room.host != user:
                    raise InvokeException(
                        "Attempted to change an item which is not owned by the user"
                    )

                if existing_item.expired:
                    raise InvokeException(
                        "Attempted to change an item which has already been played"
                    )

                # TODO: mods validation
                item.owner_id = user.user_id
                item.star = float(beatmap.difficulty_rating)
                item.order = existing_item.order

                await Playlist.update(item, self.room.room_id, session)

                # Update item in playlist
                for idx, playlist_item in enumerate(self.room.playlist):
                    if playlist_item.id == item.id:
                        self.room.playlist[idx] = item
                        break

                await self.hub.playlist_changed(
                    self.server_room,
                    item,
                    beatmap_changed=item.checksum != existing_item.checksum,
                )

    async def remove_item(self, playlist_item_id: int, user: MultiplayerRoomUser):
        from app.database import Playlist

        item = next(
            (i for i in self.room.playlist if i.id == playlist_item_id),
            None,
        )

        if item is None:
            raise InvokeException("Item does not exist in the room")

        # Check if it's the only item and current item
        if item == self.current_item:
            upcoming_items = [i for i in self.room.playlist if not i.expired]
            if len(upcoming_items) == 1:
                raise InvokeException("The only item in the room cannot be removed")

        if item.owner_id != user.user_id and self.room.host != user:
            raise InvokeException(
                "Attempted to remove an item which is not owned by the user"
            )

        if item.expired:
            raise InvokeException(
                "Attempted to remove an item which has already been played"
            )

        async with AsyncSession(engine) as session:
            await Playlist.delete_item(item.id, self.room.room_id, session)

        self.room.playlist.remove(item)
        self.current_index = self.room.playlist.index(self.upcoming_items[0])

        await self.update_order()
        await self.update_current_item()
        await self.hub.playlist_removed(self.server_room, item.id)

    @property
    def current_item(self):
        """Get the current playlist item"""
        current_id = self.room.settings.playlist_item_id
        return next(
            (item for item in self.room.playlist if item.id == current_id),
            None,
        )


@dataclass
class ServerMultiplayerRoom:
    room: MultiplayerRoom
    category: RoomCategory
    status: RoomStatus
    start_at: datetime.datetime
    queue: MultiplayerQueue | None = None
