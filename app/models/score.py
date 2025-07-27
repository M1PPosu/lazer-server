from __future__ import annotations

from enum import Enum
import json
from typing import Any, Literal, TypedDict

from app.path import STATIC_DIR

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


class APIMod(TypedDict, total=False):
    acronym: str
    settings: dict[str, Any]


legacy_mod: dict[str, int] = {
    "NF": 1 << 0,  # No Fail
    "EZ": 1 << 1,  # Easy
    "TD": 1 << 2,  # Touch Device
    "HD": 1 << 3,  # Hidden
    "HR": 1 << 4,  # Hard Rock
    "SD": 1 << 5,  # Sudden Death
    "DT": 1 << 6,  # Double Time
    "RX": 1 << 7,  # Relax
    "HT": 1 << 8,  # Half Time
    "NC": 1 << 9,  # Nightcore
    "FL": 1 << 10,  # Flashlight
    "AT": 1 << 11,  # Autoplay
    "SO": 1 << 12,  # Spun Out
    "AP": 1 << 13,  # Auto Pilot
    "PF": 1 << 14,  # Perfect
    "4K": 1 << 15,  # 4K
    "5K": 1 << 16,  # 5K
    "6K": 1 << 17,  # 6K
    "7K": 1 << 18,  # 7K
    "8K": 1 << 19,  # 8K
    "FI": 1 << 20,  # Fade In
    "RD": 1 << 21,  # Random
    "CN": 1 << 22,  # Cinema
    "TP": 1 << 23,  # Target Practice
    "9K": 1 << 24,  # 9K
    "CO": 1 << 25,  # Key Co-op
    "1K": 1 << 26,  # 1K
    "3K": 1 << 27,  # 3K
    "2K": 1 << 28,  # 2K
    "SV2": 1 << 29,  # ScoreV2
    "MR": 1 << 30,  # Mirror
}
legacy_mod["NC"] |= legacy_mod["DT"]
legacy_mod["PF"] |= legacy_mod["SD"]


def api_mod_to_int(mods: list[APIMod]) -> int:
    sum_ = 0
    for mod in mods:
        sum_ |= legacy_mod.get(mod["acronym"], 0)
    return sum_


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


# see static/mods.json
class Settings(TypedDict):
    Name: str
    Type: str
    Label: str
    Description: str


class Mod(TypedDict):
    Acronym: str
    Name: str
    Description: str
    Type: str
    Settings: list[Settings]
    IncompatibleMods: list[str]
    RequiresConfiguration: bool
    UserPlayable: bool
    ValidForMultiplayer: bool
    ValidForFreestyleAsRequiredMod: bool
    ValidForMultiplayerAsFreeMod: bool
    AlwaysValidForSubmission: bool


MODS: dict[int, dict[str, Mod]] = {}

ScoreStatistics = dict[HitResult, int]


def _init_mods():
    mods_file = STATIC_DIR / "mods.json"
    raw_mods = json.loads(mods_file.read_text())
    for ruleset in raw_mods:
        ruleset_mods = {}
        for mod in ruleset["Mods"]:
            ruleset_mods[mod["Acronym"]] = mod
        MODS[ruleset["RulesetID"]] = ruleset_mods


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
        if not MODS:
            _init_mods()
        incompatible_mods = set()
        # check incompatible mods
        for mod in mods:
            if mod["acronym"] in incompatible_mods:
                raise ValueError(
                    f"Mod {mod['acronym']} is incompatible with other mods"
                )
            setting_mods = MODS[info.data["ruleset_id"]].get(mod["acronym"])
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
