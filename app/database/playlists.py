from datetime import datetime
from typing import TYPE_CHECKING

from app.models.model import UTCBaseModel
from app.models.mods import APIMod, msgpack_to_apimod
from app.models.multiplayer_hub import PlaylistItem

from .beatmap import Beatmap, BeatmapResp

from sqlmodel import (
    JSON,
    BigInteger,
    Column,
    DateTime,
    Field,
    ForeignKey,
    Relationship,
    SQLModel,
)

if TYPE_CHECKING:
    from .room import Room


class PlaylistBase(SQLModel, UTCBaseModel):
    id: int = 0
    owner_id: int = Field(sa_column=Column(BigInteger, ForeignKey("lazer_users.id")))
    ruleset_id: int = Field(ge=0, le=3)
    expired: bool = Field(default=False)
    playlist_order: int = Field(default=0)
    played_at: datetime | None = Field(
        sa_column=Column(DateTime(timezone=True)),
        default=None,
    )
    allowed_mods: list[APIMod] = Field(
        default_factory=list,
        sa_column=Column(JSON),
    )
    required_mods: list[APIMod] = Field(
        default_factory=list,
        sa_column=Column(JSON),
    )
    beatmap_id: int = Field(
        foreign_key="beatmaps.id",
    )
    freestyle: bool = Field(default=False)


class Playlist(PlaylistBase, table=True):
    __tablename__ = "room_playlists"  # pyright: ignore[reportAssignmentType]
    db_id: int = Field(default=None, primary_key=True, index=True, exclude=True)
    room_id: int = Field(foreign_key="rooms.id", exclude=True)

    beatmap: Beatmap = Relationship(
        sa_relationship_kwargs={
            "lazy": "joined",
        }
    )
    room: "Room" = Relationship()

    @classmethod
    async def from_hub(cls, playlist: PlaylistItem, room_id: int) -> "Playlist":
        return cls(
            id=playlist.id,
            owner_id=playlist.owner_id,
            ruleset_id=playlist.ruleset_id,
            beatmap_id=playlist.beatmap_id,
            required_mods=[msgpack_to_apimod(mod) for mod in playlist.required_mods],
            allowed_mods=[msgpack_to_apimod(mod) for mod in playlist.allowed_mods],
            expired=playlist.expired,
            playlist_order=playlist.order,
            played_at=playlist.played_at,
            freestyle=playlist.freestyle,
            room_id=room_id,
        )


class PlaylistResp(PlaylistBase):
    beatmap: BeatmapResp | None = None

    @classmethod
    async def from_db(cls, playlist: Playlist) -> "PlaylistResp":
        resp = cls.model_validate(playlist)
        resp.beatmap = await BeatmapResp.from_db(playlist.beatmap)
        return resp
