from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from app.database.beatmap import Beatmap
from app.models.mods import APIMod
from app.models.user import APIUser

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


class MultiplayerRoomState(str, Enum):
    OPEN = "open"
    WAITING_FOR_LOAD = "waiting_for_load"
    PLAYING = "playing"
    CLOSED = "closed"


class MultiplayerUserState(str, Enum):
    IDLE = "idle"
    READY = "ready"
    WAITING_FOR_LOAD = "waiting_for_load"
    LOADED = "loaded"
    READY_FOR_GAMEPLAY = "ready_for_gameplay"
    PLAYING = "playing"
    FINISHED_PLAY = "finished_play"
    RESULTS = "results"
    SPECTATING = "spectating"


class DownloadState(str, Enum):
    UNKONWN = "unkown"
    NOT_DOWNLOADED = "not_downloaded"
    DOWNLOADING = "downloading"
    IMPORTING = "importing"
    LOCALLY_AVAILABLE = "locally_available"


class BeatmapAvailability(BaseModel):
    state: DownloadState
    downloadProgress: float | None


class MultiplayerPlaylistItem(BaseModel):
    id: int = 0
    ownerId: int = 0
    beatmapId: int = 0
    beatmapChecksum: str = ""
    rulesetId: int = 0
    requiredMods: list[APIMod] = []
    allowedMods: list[APIMod] = []
    expired: bool = False
    playlistOrder: int = 0
    playedAt: datetime | None
    starRating: float = 0.0
    freestyle: bool = False


class MultiplayerRoomSettings(BaseModel):
    name: str = "Unnamed room"
    playlistItemId: int = 0
    password: str = ""
    matchType: MatchType = MatchType.HEAD_TO_HEAD
    queueMode: QueueMode = QueueMode.HOST_ONLY
    autoStartDuration: timedelta = timedelta(0)
    autoSkip: bool = False


class MultiplayerRoomUser(BaseModel):
    id: int
    state: MultiplayerUserState = MultiplayerUserState.IDLE
    beatmapAvailability: BeatmapAvailability = BeatmapAvailability(
        state=DownloadState.UNKONWN, downloadProgress=None
    )
    mods: list[APIMod] = []
    matchState: dict[str, Any] | None
    rulesetId: int | None
    beatmapId: int | None


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


class MultiplayerCountdown(BaseModel):
    id: int
    timeRemaining: timedelta


class Room(BaseModel):
    id: int | None
    name: str = ""
    password: str | None
    has_password: bool = False
    host: APIUser
    category: RoomCategory = RoomCategory.NORMAL
    duration: int | None
    starts_at: datetime | None
    ends_at: datetime | None
    participant_count: int = 0
    recent_participants: list[APIUser] = []
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

    @classmethod
    def from_MultiplayerRoom(cls, room: MultiplayerRoom):
        r = cls.model_validate(room.model_dump())
        r.id = room.roomId
        r.name = room.settings.name
        r.password = room.settings.password
        r.has_password = bool(room.settings.password)
        if room.host:
            r.host.id = room.host.id
        r.type = room.settings.matchType
        r.queue_mode = room.settings.queueMode
        r.auto_start_duration = room.settings.autoStartDuration.seconds
        r.auto_skip = room.settings.autoSkip
        r.channel_id = room.channelId
        if room.state == MultiplayerRoomState.OPEN:
            r.status = RoomStatus.IDLE
        elif (
            room.state == MultiplayerRoomState.WAITING_FOR_LOAD
            or room.state == MultiplayerRoomState.PLAYING
        ):
            r.status = RoomStatus.PLAYING
        elif room.state == MultiplayerRoomState.CLOSED:
            r.status = RoomStatus.IDLE
            r.ends_at = datetime.utcnow()
        playlist_items = []
        for multiplayer_item in room.playlist:
            playlist_item = PlaylistItem(
                id=multiplayer_item.id,
                owner_id=multiplayer_item.ownerId,
                ruleset_id=multiplayer_item.rulesetId,
                expired=multiplayer_item.expired,
                playlist_order=multiplayer_item.playlistOrder,
                played_at=multiplayer_item.playedAt,
                freestyle=multiplayer_item.freestyle,
                beatmap_id=multiplayer_item.beatmapId,
                beatmap=None,
            )
            playlist_items.append(playlist_item)
        r.playlist = playlist_items
        r.participant_count = len(playlist_items)
        return r


class MultiplayerRoom(BaseModel):
    roomId: int
    state: MultiplayerRoomState = MultiplayerRoomState.OPEN
    settings: MultiplayerRoomSettings = MultiplayerRoomSettings()
    users: list[MultiplayerRoomUser] = []
    host: MultiplayerRoomUser | None
    matchState: dict[str, Any] | None
    playlist: list[MultiplayerPlaylistItem] = []
    activeCountdowns: list[MultiplayerCountdown] = []
    channelId: int = 0

    def __init__(self, roomId: int, **data):
        super().__init__(roomId=roomId, **data)
