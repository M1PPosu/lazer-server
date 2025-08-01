from __future__ import annotations

import datetime
from typing import Annotated, Any, Literal

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
from pydantic import BaseModel, Field, field_serializer, field_validator


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


class ServerMultiplayerRoom(BaseModel):
    room: MultiplayerRoom
    category: RoomCategory
    status: RoomStatus
    start_at: datetime.datetime
