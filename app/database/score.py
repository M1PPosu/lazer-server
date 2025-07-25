# ruff: noqa: I002

from datetime import datetime
import math
from typing import Literal

from app.models.score import Rank

from .beatmap import Beatmap
from .beatmapset import Beatmapset
from .user import User

from pydantic import BaseModel
from sqlalchemy import Column, DateTime
from sqlmodel import BigInteger, Field, Relationship, SQLModel


class ScoreBase(SQLModel):
    # 基本字段
    accuracy: float
    beatmap_id: int = Field(index=True, foreign_key="_beatmap.id")
    map_md5: str = Field(max_length=32, index=True)
    best_id: int | None = Field(default=None)
    build_id: int | None = Field(default=None)
    classic_total_score: int | None = Field(
        default=0, sa_column=Column(BigInteger)
    )  # solo_score
    ended_at: datetime = Field(sa_column=Column(DateTime))
    has_replay: bool
    max_combo: int
    mods: int = Field(index=True)
    passed: bool
    playlist_item_id: int | None = Field(default=None)  # multiplayer
    pp: float
    preserve: bool = Field(default=True)
    rank: Rank
    room_id: int | None = Field(default=None)  # multiplayer
    ruleset_id: Literal[0, 1, 2, 3] = Field(index=True)
    started_at: datetime = Field(sa_column=Column(DateTime))
    total_score: int = Field(default=0, sa_column=Column(BigInteger))
    type: str
    user_id: int = Field(foreign_key="user.id", index=True)
    # ScoreStatistics
    n300: int = Field(default=0, exclude=True)
    n100: int
    n50: int
    nmiss: int
    ngeki: int
    nkatu: int
    nlarge_tick_miss: int | None = Field(default=None, exclude=True)
    nslider_tail_hit: int | None = Field(default=None, exclude=True)

    # optional
    beatmap: "Beatmap" = Relationship(back_populates="scores")
    beatmapset: "Beatmapset" = Relationship(back_populates="scores")
    # TODO: current_user_attributes
    position: int | None = Field(default=None)  # multiplayer
    user: "User" = Relationship(back_populates="scores")


class ScoreStatistics(BaseModel):
    count_miss: int
    count_50: int
    count_100: int
    count_300: int
    count_geki: int
    count_katu: int
    count_large_tick_miss: int | None = None
    count_slider_tail_hit: int | None = None


class Score(ScoreBase, table=True):
    __tablename__ = "scores"  # pyright: ignore[reportAssignmentType]
    id: int = Field(primary_key=True)


class ScoreResp(ScoreBase):
    id: int
    is_perfect_combo: bool = False
    legacy_perfect: bool = False
    legacy_total_score: int = 0  # FIXME
    processed: bool = False  # solo_score
    weight: float = 0.0
    statistics: ScoreStatistics | None = None

    @classmethod
    def from_db(cls, score: Score) -> "ScoreResp":
        s = cls.model_validate(score)
        s.is_perfect_combo = s.max_combo == s.beatmap.max_combo
        s.legacy_perfect = s.max_combo == s.beatmap.max_combo
        if score.best_id:
            # https://osu.ppy.sh/wiki/Performance_points/Weighting_system
            s.weight = math.pow(0.95, score.best_id)
        s.statistics = ScoreStatistics(
            count_miss=score.nmiss,
            count_50=score.n50,
            count_100=score.n100,
            count_300=score.n300,
            count_geki=score.ngeki,
            count_katu=score.nkatu,
            count_large_tick_miss=score.nlarge_tick_miss,
            count_slider_tail_hit=score.nslider_tail_hit,
        )
        return s
