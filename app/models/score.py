from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Literal, TypedDict

from .mods import API_MODS, APIMod, init_mods

from pydantic import BaseModel, Field, ValidationInfo, field_validator

if TYPE_CHECKING:
    import rosu_pp_py as rosu


class GameMode(str, Enum):
    OSU = "osu"
    TAIKO = "taiko"
    FRUITS = "fruits"
    MANIA = "mania"
    OSURX = "osurx"
    OSUAP = "osuap"

    def to_rosu(self) -> "rosu.GameMode":
        import rosu_pp_py as rosu

        return {
            GameMode.OSU: rosu.GameMode.Osu,
            GameMode.TAIKO: rosu.GameMode.Taiko,
            GameMode.FRUITS: rosu.GameMode.Catch,
            GameMode.MANIA: rosu.GameMode.Mania,
            GameMode.OSURX: rosu.GameMode.Osu,
            GameMode.OSUAP: rosu.GameMode.Osu,
        }[self]


MODE_TO_INT = {
    GameMode.OSU: 0,
    GameMode.TAIKO: 1,
    GameMode.FRUITS: 2,
    GameMode.MANIA: 3,
    GameMode.OSURX: 0,
    GameMode.OSUAP: 0,
}
INT_TO_MODE = {v: k for k, v in MODE_TO_INT.items()}
INT_TO_MODE[0] = GameMode.OSU


class Rank(str, Enum):
    X = "X"
    XH = "XH"
    S = "S"
    SH = "SH"
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    F = "F"

    @property
    def in_statisctics(self):
        return self in {
            Rank.X,
            Rank.XH,
            Rank.S,
            Rank.SH,
            Rank.A,
        }


# https://github.com/ppy/osu/blob/master/osu.Game/Rulesets/Scoring/HitResult.cs
class HitResult(str, Enum):
    NONE = "none"  # [Order(15)]

    MISS = "miss"  # [Order(5)]
    MEH = "meh"  # [Order(4)]
    OK = "ok"  # [Order(3)]
    GOOD = "good"  # [Order(2)]
    GREAT = "great"  # [Order(1)]
    PERFECT = "perfect"  # [Order(0)]

    SMALL_TICK_MISS = "small_tick_miss"  # [Order(12)]
    SMALL_TICK_HIT = "small_tick_hit"  # [Order(7)]
    LARGE_TICK_MISS = "large_tick_miss"  # [Order(11)]
    LARGE_TICK_HIT = "large_tick_hit"  # [Order(6)]

    SMALL_BONUS = "small_bonus"  # [Order(10)]
    LARGE_BONUS = "large_bonus"  # [Order(9)]

    IGNORE_MISS = "ignore_miss"  # [Order(14)]
    IGNORE_HIT = "ignore_hit"  # [Order(13)]

    COMBO_BREAK = "combo_break"  # [Order(16)]

    SLIDER_TAIL_HIT = "slider_tail_hit"  # [Order(8)]

    LEGACY_COMBO_INCREASE = "legacy_combo_increase"  # [Order(99)] @deprecated

    def is_hit(self) -> bool:
        return self not in (
            HitResult.NONE,
            HitResult.IGNORE_MISS,
            HitResult.COMBO_BREAK,
            HitResult.LARGE_TICK_MISS,
            HitResult.SMALL_TICK_MISS,
            HitResult.MISS,
        )


class LeaderboardType(Enum):
    GLOBAL = "global"
    FRIENDS = "friend"
    COUNTRY = "country"
    TEAM = "team"


ScoreStatistics = dict[HitResult, int]


class SoloScoreSubmissionInfo(BaseModel):
    rank: Rank
    total_score: int = Field(ge=0, le=2**31 - 1)
    total_score_without_mods: int = Field(ge=0, le=2**31 - 1)
    accuracy: float = Field(ge=0, le=1)
    pp: float = Field(default=0, ge=0, le=2**31 - 1)
    max_combo: int = 0
    ruleset_id: Literal[0, 1, 2, 3]
    passed: bool = False
    mods: list[APIMod] = Field(default_factory=list)
    statistics: ScoreStatistics = Field(default_factory=dict)
    maximum_statistics: ScoreStatistics = Field(default_factory=dict)

    @field_validator("mods", mode="after")
    @classmethod
    def validate_mods(cls, mods: list[APIMod], info: ValidationInfo):
        if not API_MODS:
            init_mods()
        incompatible_mods = set()
        # check incompatible mods
        for mod in mods:
            if mod["acronym"] in incompatible_mods:
                raise ValueError(
                    f"Mod {mod['acronym']} is incompatible with other mods"
                )
            setting_mods = API_MODS[info.data["ruleset_id"]].get(mod["acronym"])
            if not setting_mods:
                raise ValueError(f"Invalid mod: {mod['acronym']}")
            incompatible_mods.update(setting_mods["IncompatibleMods"])
        return mods


class LegacyReplaySoloScoreInfo(TypedDict):
    online_id: int
    mods: list[APIMod]
    statistics: ScoreStatistics
    maximum_statistics: ScoreStatistics
    client_version: str
    rank: Rank
    user_id: int
    total_score_without_mods: int
