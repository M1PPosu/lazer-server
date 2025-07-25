from enum import Enum, IntEnum
from typing import Any, Optional
from pydantic import BaseModel
from datetime import datetime
from .user import User

class GameMode(str, Enum):
    OSU = "osu"
    TAIKO = "taiko"
    FRUITS = "fruits"
    MANIA = "mania"

class APIMod(BaseModel):
    acronym: str
    settings: dict[str, Any] = {}

# https://github.com/ppy/osu/blob/master/osu.Game/Rulesets/Scoring/HitResult.cs
class HitResult(IntEnum):
    PERFECT = 0  # [Order(0)]
    GREAT = 1  # [Order(1)]
    GOOD = 2  # [Order(2)]
    OK = 3  # [Order(3)]
    MEH = 4  # [Order(4)]
    MISS = 5  # [Order(5)]

    LARGE_TICK_HIT = 6  # [Order(6)]
    SMALL_TICK_HIT = 7  # [Order(7)]
    SLIDER_TAIL_HIT = 8  # [Order(8)]

    LARGE_BONUS = 9  # [Order(9)]
    SMALL_BONUS = 10  # [Order(10)]

    LARGE_TICK_MISS = 11  # [Order(11)]
    SMALL_TICK_MISS = 12  # [Order(12)]

    IGNORE_HIT = 13  # [Order(13)]
    IGNORE_MISS = 14  # [Order(14)]

    NONE = 15  # [Order(15)]
    COMBO_BREAK = 16  # [Order(16)]

    LEGACY_COMBO_INCREASE = 99  # [Order(99)] @deprecated

class Score(BaseModel):
    # 基本信息
    id: int
    user_id: int
    mode: GameMode
    mode_int: int
    beatmap_id: int
    best_id: int
    build_id: int

    # 分数和准确度
    score: int
    accuracy: float
    mods: list[APIMod]
    total_score: int
    
    # 命中统计
    statistics: dict[HitResult, int]
    maximum_statistics: dict[HitResult, int]
    
    # 排名相关
    rank: str  # 等级 (SS, S, A, B, C, D, F)
    ranked: bool
    rank_country: Optional[int] = None
    rank_global: Optional[int] = None
    
    # PP值
    pp: Optional[float] = None
    pp_exp: Optional[float] = None
    
    # 连击
    maximum_combo: int
    combo: int
    
    # 游戏设置
    is_perfect_combo: bool
    passed: bool   # 是否通过谱面
    
    # 时间信息
    started_at: datetime
    ended_at: datetime
    
    # 最佳成绩相关
    best_id: Optional[int] = None
    is_best: bool = False
    
    # 额外信息
    has_replay: bool  # 是否有回放
    preserve: bool  # 是否保留
    processed: bool  # 是否已处理
    
    # Legacy字段
    legacy_score_id: Optional[int] = None
    legacy_total_score: int
    legacy_perfect: bool

    # mp字段