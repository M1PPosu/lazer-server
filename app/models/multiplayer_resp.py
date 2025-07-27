from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum

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
    id: int
    OwnerID: int
    RulesetID: int
    Expired: bool
    PlaylistOrder: int | None
    PlayedAt: datetime | None
    AllowedMods: list[APIMod] = []
    RequiredMods: list[APIMod] = []
    Freestyle: bool


class RoomPlaylistItemStats(BaseModel):
    CountActive: int
    CountTotal: int
    RulesetIDs: list[int]


class RoomDifficulityRange(BaseModel):
    Min: float
    Max: float


class ItemAttempsCount(BaseModel):
    PlaylistItemID: int
    Attemps: int
    Passed: bool


class PlaylistAggregateScore(BaseModel):
    PlaylistItemAttempts: list[ItemAttempsCount]


class RoomStatus(int, Enum):
    Idle = 0
    Playing = 1


class RoomAvilability(int, Enum):
    Public = 0
    FriendsOnly = 1
    InviteOnly = 2


class RoomResp(BaseModel):
    RoomID: int
    Name: str = ""
    Password: str | None
    Has_Password: bool
    Host: User | None
    Category: RoomCategory
    Duration: timedelta | None
    StartDate: datetime | None
    EndDate: datetime | None
    MaxParticipants: int | None
    ParticipantCount: int
    RecentParticipants: list[User] = []
    Type: MatchType
    MaxAttemps: int | None
    Playlist: list[RespPlaylistItem]
    PlaylistItemStatus: RoomPlaylistItemStats
    DifficulityRange: RoomDifficulityRange
    QueueMode: QueueMode
    AutoSkip: bool
    AutoStartDuration: timedelta
    UserScore: (
        PlaylistAggregateScore | None
    )  # osu.Game/Online/Rooms/Room.cs:221 原文如此，不知道为什么
    CurrentPlaylistItem: RespPlaylistItem
    ChannelID: int
    Status: RoomStatus
    Availabiliity: RoomAvilability
