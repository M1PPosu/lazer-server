from __future__ import annotations

from datetime import datetime
from enum import Enum

from app.database.beatmap import Beatmap
from app.database.user import User
from app.models.mods import APIMod

from pydantic import BaseModel


class RoomCategory(str, Enum):
    NORMAL = "normal"
    SPOTLIGHT = "spotlight"
    FEATURED_ARTIST = "featured_artist"
    DAILY_CHALLENGE = "daily_challenge"


class MatchType(str, Enum):
    PLAYLISTS = "playlists"
    HEAD_TO_HEAD = "head_to_head"
    TEAM_VERSUS = "team_versus"


class QueueMode(str, Enum):
    HOST_ONLY = "host_only"
    ALL_PLAYERS = "all_players"
    ALL_PLAYERS_ROUND_ROBIN = "all_players_round_robin"


class RoomAvailability(str, Enum):
    PUBLIC = "public"
    FRIENDS_ONLY = "friends_only"
    INVITE_ONLY = "invite_only"


class RoomStatus(str, Enum):
    IDLE = "idle"
    PLAYING = "playing"


class PlaylistItem(BaseModel):
    id: int | None
    owner_id: int
    ruleset_id: int
    expired: bool
    playlist_order: int | None
    played_at: datetime | None
    allowed_mods: list[APIMod] = []
    required_mods: list[APIMod] = []
    beatmap_id: int
    beatmap: Beatmap | None
    freestyle: bool


class RoomPlaylistItemStats(BaseModel):
    count_active: int
    count_total: int
    ruleset_ids: list[int] = []


class RoomDifficultyRange(BaseModel):
    min: float
    max: float


class ItemAttemptsCount(BaseModel):
    id: int
    attempts: int
    passed: bool


class PlaylistAggregateScore(BaseModel):
    playlist_item_attempts: list[ItemAttemptsCount]


class Room(BaseModel):
    id: int | None
    name: str = ""
    password: str | None
    has_password: bool = False
    host: User | None
    category: RoomCategory = RoomCategory.NORMAL
    duration: int | None
    starts_at: datetime | None
    ends_at: datetime | None
    participant_count: int = 0
    recent_participants: list[User] = []
    max_attempts: int | None
    playlist: list[PlaylistItem] = []
    playlist_item_stats: RoomPlaylistItemStats | None
    difficulty_range: RoomDifficultyRange | None
    type: MatchType = MatchType.PLAYLISTS
    queue_mode: QueueMode = QueueMode.HOST_ONLY
    auto_skip: bool = False
    auto_start_duration: int = 0
    current_user_score: PlaylistAggregateScore | None
    current_playlist_item: PlaylistItem | None
    channel_id: int = 0
    status: RoomStatus = RoomStatus.IDLE
    # availability 字段在当前序列化中未包含，但可能在某些场景下需要
    availability: RoomAvailability | None
