# mp 房间相关模型
from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum

from app.models.mods import APIMod

from pydantic import BaseModel
from sqlmodel import Double

# 数据结构定义来自osu/osu.Game/Online/Multiplayer*.cs


class MultiplayerRoomState(int, Enum):
    Open = 0
    WaitingForLoad = 1
    Playing = 2
    Closed = 3


class MatchType(int, Enum):
    Playlists = 0
    HeadToHead = 1
    TeamVersus = 2


class QueueMode(int, Enum):
    HostOnly = 0
    Allplayers = 1
    AllplayersRoundRobin = 2


class MultiPlayerRoomSettings(BaseModel):
    name: str = "Unnamed room"  # 来自osu/osu.Game/Online/MultiplayerRoomSettings.cs:15
    playlist_item_id: int
    password: str
    match_type: MatchType
    queue_mode: QueueMode
    auto_start_duration: timedelta
    auto_skip: bool


class MultiPlayerUserState(int, Enum):
    Idle = 0
    Ready = 1
    WaitingForLoad = 2
    Loaded = 3
    ReadyForGameplay = 4
    Playing = 5
    FinishedPlay = 6
    Results = 7
    Spectating = 8


class DownloadeState(int, Enum):
    Unkown = 0
    NotDownloaded = 1
    Downloading = 2
    Importing = 3
    LocallyAvailable = 4


class BeatmapAvailability(BaseModel):
    state: DownloadeState
    download_progress: float


class MatchUserState(BaseModel):
    pass


class MatchRoomState(BaseModel):
    pass


class MultiPlayerRoomUser(BaseModel):
    user_id: int
    state: MultiPlayerUserState = MultiPlayerUserState.Idle
    mods: APIMod = APIMod(acronym="", settings={})
    match_state: MatchUserState | None
    rule_set_id: int | None  # 非空则用户本地有自定义模式
    beatmap_id: int | None  # 非空则用户本地自定义谱面


class MultiplayerPlaylistItem(BaseModel):
    id: int
    owner_id: int
    beatmap_id: int
    beatmap_checksum: str = ""
    ruleset_id: int
    requierd_mods: list[APIMod] = []
    allowed_mods: list[APIMod] = []
    play_list_order: int
    played_at: datetime | None
    star_rating: Double
    free_style: bool
    OwnerID: int
    BeatmapID: int
    BeatmapChecksum: str = ""
    RulesetID: int
    RequierdMods: list[APIMod] = []
    AllowedMods: list[APIMod] = []
    PlayListOrder: int
    PlayedAt: datetime | None
    StarRating: Double
    FreeStyle: bool


class MultiplayerCountdown(BaseModel):
    id: int
    time_raming: timedelta


class MultiplayerRoom(BaseModel):
    room_id: int
    state: MultiplayerRoomState
    settings: MultiPlayerRoomSettings
    users: list[MultiPlayerRoomUser]
    host: MultiPlayerRoomUser | None
    match_state: MatchUserState
    playlist: list[MultiplayerPlaylistItem]
    active_conutdowns: list[MultiplayerCountdown]
    channel_id: int
