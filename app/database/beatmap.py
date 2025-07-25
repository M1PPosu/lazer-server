# ruff: noqa: I002
from datetime import datetime

from app.models.beatmap import BeatmapRankStatus
from app.models.score import MODE_TO_INT, GameMode

from .beatmapset import Beatmapset, BeatmapsetResp

from sqlalchemy import DECIMAL, Column, DateTime
from sqlmodel import VARCHAR, Field, Relationship, SQLModel


class BeatmapOwner(SQLModel):
    id: int
    username: str


class BeatmapBase(SQLModel):
    # Beatmap
    url: str
    mode: GameMode
    beatmapset_id: int = Field(foreign_key="beatmapsets.id", index=True)
    difficulty_rating: float = Field(
        default=0.0, sa_column=Column(DECIMAL(precision=10, scale=6))
    )
    beatmap_status: BeatmapRankStatus
    total_length: int
    user_id: int
    version: str

    # optional
    checksum: str = Field(sa_column=Column(VARCHAR(32), index=True))
    current_user_playcount: int = Field(default=0)
    max_combo: int = Field(default=0)
    # TODO: failtimes, owners

    # BeatmapExtended
    ar: float = Field(default=0.0, sa_column=Column(DECIMAL(precision=10, scale=2)))
    cs: float = Field(default=0.0, sa_column=Column(DECIMAL(precision=10, scale=2)))
    drain: float = Field(
        default=0.0,
        sa_column=Column(DECIMAL(precision=10, scale=2)),
    )  # hp
    accuracy: float = Field(
        default=0.0,
        sa_column=Column(DECIMAL(precision=10, scale=2)),
    )  # od
    bpm: float = Field(default=0.0, sa_column=Column(DECIMAL(precision=10, scale=2)))
    count_circles: int = Field(default=0)
    count_sliders: int = Field(default=0)
    count_spinners: int = Field(default=0)
    deleted_at: datetime | None = Field(default=None, sa_column=Column(DateTime))
    hit_length: int = Field(default=0)
    last_updated: datetime = Field(sa_column=Column(DateTime))
    passcount: int = Field(default=0)
    playcount: int = Field(default=0)


class Beatmap(BeatmapBase, table=True):
    __tablename__ = "beatmaps"  # pyright: ignore[reportAssignmentType]
    id: int | None = Field(default=None, primary_key=True, index=True)
    beatmapset_id: int = Field(foreign_key="beatmapsets.id", index=True)
    # optional
    beatmapset: Beatmapset = Relationship(back_populates="beatmaps")


class BeatmapResp(BeatmapBase):
    id: int
    beatmapset_id: int
    beatmapset: BeatmapsetResp | None = None
    convert: bool = False
    is_scoreable: bool
    status: str
    mode_int: int
    ranked: int
    url: str = ""

    @classmethod
    def from_db(
        cls,
        beatmap: Beatmap,
        query_mode: GameMode | None = None,
        from_set: bool = False,
    ) -> "BeatmapResp":
        beatmap_ = beatmap.model_dump()
        if query_mode is not None and beatmap.mode != query_mode:
            beatmap_["convert"] = True
        beatmap_["is_scoreable"] = beatmap.beatmap_status > BeatmapRankStatus.PENDING
        beatmap_["status"] = beatmap.beatmap_status.name.lower()
        beatmap_["ranked"] = beatmap.beatmap_status.value
        beatmap_["mode_int"] = MODE_TO_INT[beatmap.mode]
        if not from_set:
            beatmap_["beatmapset"] = BeatmapsetResp.from_db(beatmap.beatmapset)
        return cls.model_validate(beatmap_)
