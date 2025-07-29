from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum

from app.database.beatmap import Beatmap, BeatmapResp
from app.database.user import User as DBUser
from app.fetcher import Fetcher
from app.models.mods import APIMod
from app.models.user import User
from app.utils import convert_db_user_to_api_user

from pydantic import BaseModel, Field
from sqlmodel.ext.asyncio.session import AsyncSession


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
    UNKOWN = "unkown"
    NOT_DOWNLOADED = "not_downloaded"
    DOWNLOADING = "downloading"
    IMPORTING = "importing"
    LOCALLY_AVAILABLE = "locally_available"


class PlaylistItem(BaseModel):
    id: int
    owner_id: int
    ruleset_id: int
    expired: bool
    playlist_order: int | None
    played_at: datetime | None
    allowed_mods: list[APIMod] = []
    required_mods: list[APIMod] = []
    beatmap_id: int
    beatmap: BeatmapResp | None
    freestyle: bool

    class Config:
        exclude_none = True

    @classmethod
    async def from_mpListItem(
        cls, item: MultiPlayerListItem, db: AsyncSession, fetcher: Fetcher
    ):
        s = cls.model_validate(item.model_dump())
        s.id = item.id
        s.owner_id = item.OwnerID
        s.ruleset_id = item.RulesetID
        s.expired = item.Expired
        s.playlist_order = item.PlaylistOrder
        s.played_at = item.PlayedAt
        s.required_mods = item.RequierdMods
        s.allowed_mods = item.AllowedMods
        s.freestyle = item.Freestyle
        cur_beatmap = await Beatmap.get_or_fetch(
            db, fetcher=fetcher, bid=item.BeatmapID
        )
        s.beatmap = BeatmapResp.from_db(cur_beatmap)
        s.beatmap_id = item.BeatmapID
        return s


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


class MultiplayerRoomSettings(BaseModel):
    Name: str = "Unnamed Room"
    PlaylistItemId: int
    Password: str = ""
    MatchType: MatchType
    QueueMode: QueueMode
    AutoStartDuration: timedelta
    AutoSkip: bool


class BeatmapAvailability(BaseModel):
    State: DownloadState
    DownloadProgress: float | None


class MatchUserState(BaseModel):
    class Config:
        extra = "allow"


class TeamVersusState(MatchUserState):
    TeamId: int


MatchUserStateType = TeamVersusState | MatchUserState


class MultiplayerRoomUser(BaseModel):
    UserID: int
    State: MultiplayerUserState = MultiplayerUserState.IDLE
    BeatmapAvailability: BeatmapAvailability
    Mods: list[APIMod] = []
    MatchUserState: MatchUserStateType | None
    RulesetId: int | None
    BeatmapId: int | None
    User: User | None

    @classmethod
    async def from_id(cls, id: int, db: AsyncSession):
        actualUser = (
            await db.exec(
                DBUser.all_select_clause().where(
                    DBUser.id == id,
                )
            )
        ).first()
        user = (
            await convert_db_user_to_api_user(actualUser)
            if actualUser is not None
            else None
        )
        return MultiplayerRoomUser(
            UserID=id,
            MatchUserState=None,
            BeatmapAvailability=BeatmapAvailability(
                State=DownloadState.UNKOWN, DownloadProgress=None
            ),
            RulesetId=None,
            BeatmapId=None,
            User=user,
        )


class MatchRoomState(BaseModel):
    class Config:
        extra = "allow"


class MultiPlayerTeam(BaseModel):
    id: int = 0
    name: str = ""


class TeamVersusRoomState(BaseModel):
    teams: list[MultiPlayerTeam] = []

    class Config:
        pass

    @classmethod
    def create_default(cls):
        return cls(
            teams=[
                MultiPlayerTeam(id=0, name="Team Red"),
                MultiPlayerTeam(id=1, name="Team Blue"),
            ]
        )


MatchRoomStateType = TeamVersusRoomState | MatchRoomState


class MultiPlayerListItem(BaseModel):
    id: int
    OwnerID: int
    BeatmapID: int
    BeatmapChecksum: str = ""
    RulesetID: int
    RequierdMods: list[APIMod]
    AllowedMods: list[APIMod]
    Expired: bool
    PlaylistOrder: int | None
    PlayedAt: datetime | None
    StarRating: float
    Freestyle: bool

    @classmethod
    async def from_apiItem(cls, item: PlaylistItem, db: AsyncSession, fetcher: Fetcher):
        s = cls.model_validate(item.model_dump())
        s.id = item.id
        s.OwnerID = item.owner_id
        if item.beatmap is None:  # 从客户端接受的一定没有这字段
            cur_beatmap = await Beatmap.get_or_fetch(
                db, fetcher=fetcher, bid=item.beatmap_id
            )
            s.BeatmapID = cur_beatmap.id if cur_beatmap.id is not None else 0
            s.BeatmapChecksum = cur_beatmap.checksum
            s.StarRating = cur_beatmap.difficulty_rating
        s.RulesetID = item.ruleset_id
        s.RequierdMods = item.required_mods
        s.AllowedMods = item.allowed_mods
        s.Expired = item.expired
        s.PlaylistOrder = item.playlist_order if item.playlist_order is not None else 0
        s.PlayedAt = item.played_at
        s.Freestyle = item.freestyle
        return s


class MultiplayerCountdown(BaseModel):
    id: int = 0
    time_remaining: timedelta = timedelta(seconds=0)
    is_exclusive: bool = True

    class Config:
        extra = "allow"


class MatchStartCountdown(MultiplayerCountdown):
    pass


class ForceGameplayStartCountdown(MultiplayerCountdown):
    pass


class ServerShuttingCountdown(MultiplayerCountdown):
    pass


MultiplayerCountdownType = (
    MatchStartCountdown
    | ForceGameplayStartCountdown
    | ServerShuttingCountdown
    | MultiplayerCountdown
)


class PlaylistStatus(BaseModel):
    count_active: int
    count_total: int
    ruleset_ids: list[int]


class MultiplayerRoom(BaseModel):
    RoomId: int
    State: MultiplayerRoomState
    Settings: MultiplayerRoomSettings = MultiplayerRoomSettings(
        PlaylistItemId=0,
        MatchType=MatchType.HEAD_TO_HEAD,
        QueueMode=QueueMode.HOST_ONLY,
        AutoStartDuration=timedelta(0),
        AutoSkip=False,
    )
    Users: list[MultiplayerRoomUser]
    Host: MultiplayerRoomUser
    MatchState: MatchRoomState | None
    Playlist: list[MultiPlayerListItem]
    ActivecCountDowns: list[MultiplayerCountdownType]
    ChannelID: int

    @classmethod
    def CanAddPlayistItem(cls, user: MultiplayerRoomUser) -> bool:
        return user == cls.Host or cls.Settings.QueueMode != QueueMode.HOST_ONLY


class Room(BaseModel):
    room_id: int
    name: str
    password: str | None
    has_password: bool = Field(exclude=True)
    host: User | None
    category: RoomCategory
    duration: int | None
    starts_at: datetime | None
    ends_at: datetime | None
    max_particapants: int | None = Field(exclude=True)
    particapant_count: int
    recent_particapants: list[User]
    type: MatchType
    max_attempts: int | None
    playlist: list[PlaylistItem]
    playlist_item_status: list[RoomPlaylistItemStats]
    difficulity_range: RoomDifficultyRange
    queue_mode: QueueMode
    auto_skip: bool
    auto_start_duration: int
    current_user_score: PlaylistAggregateScore | None
    current_playlist_item: PlaylistItem | None
    channel_id: int
    status: RoomStatus
    availability: RoomAvailability = Field(exclude=True)

    class Config:
        exclude_none = True

    @classmethod
    async def from_mpRoom(
        cls, room: MultiplayerRoom, db: AsyncSession, fetcher: Fetcher
    ):
        s = cls.model_validate(room.model_dump())
        s.room_id = room.RoomId
        s.name = room.Settings.Name
        s.password = room.Settings.Password
        s.type = room.Settings.MatchType
        s.queue_mode = room.Settings.QueueMode
        s.auto_skip = room.Settings.AutoSkip
        s.host = room.Host.User
        s.playlist = [
            await PlaylistItem.from_mpListItem(item, db, fetcher)
            for item in room.Playlist
        ]
        return s
