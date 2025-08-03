from datetime import UTC, datetime

from app.models.multiplayer_hub import ServerMultiplayerRoom
from app.models.room import (
    MatchType,
    QueueMode,
    RoomCategory,
    RoomDifficultyRange,
    RoomPlaylistItemStats,
    RoomStatus,
)

from .lazer_user import User, UserResp
from .playlist_attempts import ItemAttemptsCount
from .playlists import Playlist, PlaylistResp

from sqlmodel import (
    BigInteger,
    Column,
    DateTime,
    Field,
    ForeignKey,
    Relationship,
    SQLModel,
)


class RoomBase(SQLModel):
    name: str = Field(index=True)
    category: RoomCategory = Field(default=RoomCategory.NORMAL, index=True)
    duration: int | None = Field(default=None)  # minutes
    starts_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
        ),
        default=datetime.now(UTC),
    )
    ended_at: datetime | None = Field(
        sa_column=Column(
            DateTime(timezone=True),
        ),
        default=None,
    )
    participant_count: int = Field(default=0)
    max_attempts: int | None = Field(default=None)  # playlists
    type: MatchType
    queue_mode: QueueMode
    auto_skip: bool
    auto_start_duration: int
    status: RoomStatus
    # TODO: channel_id
    # recent_participants: list[User]


class Room(RoomBase, table=True):
    __tablename__ = "rooms"  # pyright: ignore[reportAssignmentType]
    id: int = Field(default=None, primary_key=True, index=True)
    host_id: int = Field(
        sa_column=Column(BigInteger, ForeignKey("lazer_users.id"), index=True)
    )

    host: User = Relationship()
    playlist: list[Playlist] = Relationship(
        sa_relationship_kwargs={
            "lazy": "joined",
            "cascade": "all, delete-orphan",
            "overlaps": "room",
        }
    )
    # playlist_item_attempts: list["ItemAttemptsCount"] = Relationship(
    #     sa_relationship_kwargs={
    #         "lazy": "joined",
    #         "cascade": "all, delete-orphan",
    #         "primaryjoin": "ItemAttemptsCount.room_id == Room.id",
    #     }
    # )


class RoomResp(RoomBase):
    id: int
    password: str | None = None
    host: UserResp | None = None
    playlist: list[PlaylistResp] = []
    playlist_item_stats: RoomPlaylistItemStats | None = None
    difficulty_range: RoomDifficultyRange | None = None
    current_playlist_item: PlaylistResp | None = None
    playlist_item_attempts: list[ItemAttemptsCount] = []

    @classmethod
    async def from_db(cls, room: Room) -> "RoomResp":
        resp = cls.model_validate(room.model_dump())

        stats = RoomPlaylistItemStats(count_active=0, count_total=0)
        difficulty_range = RoomDifficultyRange(
            min=0,
            max=0,
        )
        rulesets = set()
        for playlist in room.playlist:
            stats.count_total += 1
            if not playlist.expired:
                stats.count_active += 1
            rulesets.add(playlist.ruleset_id)
            difficulty_range.min = min(
                difficulty_range.min, playlist.beatmap.difficulty_rating
            )
            difficulty_range.max = max(
                difficulty_range.max, playlist.beatmap.difficulty_rating
            )
            resp.playlist.append(await PlaylistResp.from_db(playlist))
        stats.ruleset_ids = list(rulesets)
        resp.playlist_item_stats = stats
        resp.difficulty_range = difficulty_range
        resp.current_playlist_item = resp.playlist[-1] if resp.playlist else None
        # resp.playlist_item_attempts = room.playlist_item_attempts

        return resp

    @classmethod
    async def from_hub(cls, server_room: ServerMultiplayerRoom) -> "RoomResp":
        room = server_room.room
        resp = cls(
            id=room.room_id,
            name=room.settings.name,
            type=room.settings.match_type,
            queue_mode=room.settings.queue_mode,
            auto_skip=room.settings.auto_skip,
            auto_start_duration=int(room.settings.auto_start_duration.total_seconds()),
            status=server_room.status,
            category=server_room.category,
            # duration = room.settings.duration,
            starts_at=server_room.start_at,
            participant_count=len(room.users),
        )
        return resp
