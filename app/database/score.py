# ruff: noqa: I002

from datetime import datetime
import math
from typing import Literal, TYPE_CHECKING, List

from app.models.score import Rank, APIMod, GameMode

from .beatmap import Beatmap, BeatmapResp
from .beatmapset import Beatmapset, BeatmapsetResp

from pydantic import BaseModel
from sqlalchemy import Column, DateTime, JSON
from sqlmodel import BigInteger, Field, Relationship, SQLModel, JSON as SQLModeJSON

if TYPE_CHECKING:
    from .user import User

class ScoreBase(SQLModel):
    # 基本字段
    accuracy: float
    map_md5: str = Field(max_length=32, index=True)
    best_id: int | None = Field(default=None)
    build_id: int | None = Field(default=None)
    classic_total_score: int | None = Field(
        default=0, sa_column=Column(BigInteger)
    )  # solo_score
    ended_at: datetime = Field(sa_column=Column(DateTime))
    has_replay: bool
    max_combo: int
    mods: list[APIMod] = Field(sa_column=Column(JSON))
    passed: bool
    playlist_item_id: int | None = Field(default=None)  # multiplayer
    pp: float
    preserve: bool = Field(default=True)
    rank: Rank
    room_id: int | None = Field(default=None)  # multiplayer
    ruleset_id: GameMode = Field(index=True)
    started_at: datetime = Field(sa_column=Column(DateTime))
    total_score: int = Field(default=0, sa_column=Column(BigInteger))
    type: str

    # optional
    # TODO: current_user_attributes
    position: int | None = Field(default=None)  # multiplayer


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
    beatmap_id: int = Field(index=True, foreign_key="beatmap.id")
    user_id: int = Field(foreign_key="user.id", index=True)
    # ScoreStatistics
    n300: int = Field(exclude=True)
    n100: int = Field(exclude=True)
    n50: int = Field(exclude=True)
    nmiss: int = Field(exclude=True)
    ngeki: int = Field(exclude=True)
    nkatu: int = Field(exclude=True)
    nlarge_tick_miss: int | None = Field(default=None, exclude=True)
    nslider_tail_hit: int | None = Field(default=None, exclude=True)

    # optional
    beatmap: "Beatmap" = Relationship(back_populates="scores")
    beatmapset: "Beatmapset" = Relationship(back_populates="scores")
    # FIXME: user: "User" = Relationship(back_populates="scores")


class ScoreResp(ScoreBase):
    id: int
    is_perfect_combo: bool = False
    legacy_perfect: bool = False
    legacy_total_score: int = 0  # FIXME
    processed: bool = False  # solo_score
    weight: float = 0.0
    beatmap: BeatmapResp | None = None
    beatmapset: BeatmapsetResp | None = None
    # FIXME: user: APIUser | None = None
    statistics: ScoreStatistics | None = None

    @classmethod
    def from_db(cls, score: Score) -> "ScoreResp":
        s = cls.model_validate(score)
        s.beatmap = BeatmapResp.from_db(score.beatmap)
        s.beatmapset = BeatmapsetResp.from_db(score.beatmap.beatmapset)
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