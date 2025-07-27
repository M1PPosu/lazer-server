from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum

from app.database.beatmap import Beatmap
from app.database.user import User
from app.models.mods import APIMod
from app.models.multiplayer import MatchType, QueueMode

from pydantic import BaseModel


class RoomCategory(int, Enum):
    Normal = 0
    Spotlight = 1
    FeaturedArtist = 2
    DailyChallenge = 3


class RespPlaylistItem(BaseModel):
    id: int | None
    owner_id: int
    ruleset_id: int
    expired: bool
    playlist_order: int | None
    played_at: datetime | None
    allowed_mods: list[APIMod] = []
    required_mods: list[APIMod] = []
    beatmap_id: int
    freestyle: bool
    beatmap: Beatmap | None


class RoomPlaylistItemStats(BaseModel):
    count_active: int
    count_total: int
    ruleset_ids: list[int]


class RoomDifficulityRange(BaseModel):
    min: float
    max: float


class ItemAttempsCount(BaseModel):
    playlist_item_id: int
    attemps: int
    passed: bool


class PlaylistAggregateScore(BaseModel):
    playlist_item_attempts: list[ItemAttempsCount]


class RoomStatus(int, Enum):
    Idle = 0
    Playing = 1


class RoomAvilability(int, Enum):
    Public = 0
    FriendsOnly = 1
    InviteOnly = 2


class RoomResp(BaseModel):
    room_id: int
    name: str = ""
    password: str | None
    has_password: bool
    host: User | None
    category: RoomCategory
    duration: timedelta | None
    start_date: datetime | None
    end_date: datetime | None
    max_participants: int | None
    participant_count: int
    recent_participants: list[User] = []
    type: MatchType
    max_attemps: int | None
    playlist: list[RespPlaylistItem]
    playlist_item_status: RoomPlaylistItemStats
    difficulity_range: RoomDifficulityRange
    queue_mode: QueueMode
    auto_skip: bool
    auto_start_duration: timedelta
    user_score: (
        PlaylistAggregateScore | None
    )  # osu.Game/Online/Rooms/Room.cs:221 原文如此，不知道为什么
    current_playlist_item: RespPlaylistItem
    channel_id: int
    status: RoomStatus
    availabiliity: RoomAvilability
