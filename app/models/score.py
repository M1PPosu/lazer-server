from __future__ import annotations

from enum import Enum
from typing import Literal, TypedDict

from .mods import API_MOD_TO_LEGACY, API_MODS, APIMod, init_mods

from pydantic import BaseModel, Field, ValidationInfo, field_validator
import rosu_pp_py as rosu


class GameMode(str, Enum):
    OSU = "osu"
    TAIKO = "taiko"
    FRUITS = "fruits"
    MANIA = "mania"

    def to_rosu(self) -> rosu.GameMode:
        return {
            GameMode.OSU: rosu.GameMode.Osu,
            GameMode.TAIKO: rosu.GameMode.Taiko,
            GameMode.FRUITS: rosu.GameMode.Catch,
            GameMode.MANIA: rosu.GameMode.Mania,
        }[self]


MODE_TO_INT = {
    GameMode.OSU: 0,
    GameMode.TAIKO: 1,
    GameMode.FRUITS: 2,
    GameMode.MANIA: 3,
}
INT_TO_MODE = {v: k for k, v in MODE_TO_INT.items()}


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


# https://github.com/ppy/osu/blob/master/osu.Game/Rulesets/Scoring/HitResult.cs
class HitResult(str, Enum):
    PERFECT = "perfect"  # [Order(0)]
    GREAT = "great"  # [Order(1)]
    GOOD = "good"  # [Order(2)]
    OK = "ok"  # [Order(3)]
    MEH = "meh"  # [Order(4)]
    MISS = "miss"  # [Order(5)]

    LARGE_TICK_HIT = "large_tick_hit"  # [Order(6)]
    SMALL_TICK_HIT = "small_tick_hit"  # [Order(7)]
    SLIDER_TAIL_HIT = "slider_tail_hit"  # [Order(8)]

    LARGE_BONUS = "large_bonus"  # [Order(9)]
    SMALL_BONUS = "small_bonus"  # [Order(10)]

    LARGE_TICK_MISS = "large_tick_miss"  # [Order(11)]
    SMALL_TICK_MISS = "small_tick_miss"  # [Order(12)]

    IGNORE_HIT = "ignore_hit"  # [Order(13)]
    IGNORE_MISS = "ignore_miss"  # [Order(14)]

    NONE = "none"  # [Order(15)]
    COMBO_BREAK = "combo_break"  # [Order(16)]

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
    FRIENDS = "friends"
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
        if not API_MOD_TO_LEGACY:
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


class LegacyReplaySoloScoreInfo(TypedDict):
    online_id: int
    mods: list[APIMod]
    statistics: ScoreStatistics
    maximum_statistics: ScoreStatistics
    client_version: str
    rank: Rank
    user_id: int
    total_score_without_mods: int
