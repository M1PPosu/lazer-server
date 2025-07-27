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
    Name: str = "Unnamed room"  # 来自osu/osu.Game/Online/MultiplayerRoomSettings.cs:15
    PlaylistItemId: int
    Password: str
    MatchType: MatchType
    QueueMode: QueueMode
    AutoStartDuration: timedelta
    AutoSkip: bool


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
    State: DownloadeState
    DownloadProgress: float


class MatchUserState(BaseModel):
    pass


class MatchRoomState(BaseModel):
    pass


class MultiPlayerRoomUser(BaseModel):
    UserID: int
    State: MultiPlayerUserState
    Mods: APIMod
    MatchState: MatchUserState | None
    RuleSetId: int | None  # 非空则用户本地有自定义模式
    BeatmapId: int | None  # 非空则用户本地自定义谱面


class MultiplayerPlaylistItem(BaseModel):
    id: int
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
    TimeRaming: timedelta


class MultiplayerRoom(BaseModel):
    RoomID: int
    State: MultiplayerRoomState
    Settings: MultiPlayerRoomSettings
    Users: list[MultiPlayerRoomUser]
    Host: MultiPlayerRoomUser | None
    MatchState: MatchUserState
    Playlist: list[MultiplayerPlaylistItem]
    ActiveConutdowns: list[MultiplayerCountdown]
    ChannelID: int
