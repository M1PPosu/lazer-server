from __future__ import annotations

import math
from typing import TYPE_CHECKING

from app.models.beatmap import BeatmapAttributes
from app.models.mods import APIMod
from app.models.score import GameMode

try:
    import rosu_pp_py as rosu
except ImportError:
    raise ImportError(
        "rosu-pp-py is not installed. "
        "Please install it.\n"
        "   Official: uv add rosu-pp-py\n"
        "   ppy-sb: uv add git+https://github.com/ppy-sb/rosu-pp-py.git"
    )

if TYPE_CHECKING:
    from app.database.score import Score


def clamp[T: int | float](n: T, min_value: T, max_value: T) -> T:
    if n < min_value:
        return min_value
    elif n > max_value:
        return max_value
    else:
        return n


def calculate_beatmap_attribute(
    beatmap: str,
    gamemode: GameMode | None = None,
    mods: int | list[APIMod] | list[str] = 0,
) -> BeatmapAttributes:
    map = rosu.Beatmap(content=beatmap)
    if gamemode is not None:
        map.convert(gamemode.to_rosu(), mods)  # pyright: ignore[reportArgumentType]
    diff = rosu.Difficulty(mods=mods).calculate(map)
    return BeatmapAttributes(
        star_rating=diff.stars,
        max_combo=diff.max_combo,
        aim_difficulty=diff.aim,
        aim_difficult_slider_count=diff.aim_difficult_slider_count,
        speed_difficulty=diff.speed,
        speed_note_count=diff.speed_note_count,
        slider_factor=diff.slider_factor,
        aim_difficult_strain_count=diff.aim_difficult_strain_count,
        speed_difficult_strain_count=diff.speed_difficult_strain_count,
        mono_stamina_factor=diff.stamina,
    )


def calculate_pp(
    score: "Score",
    beatmap: str,
) -> float:
    map = rosu.Beatmap(content=beatmap)
    map.convert(score.gamemode.to_rosu(), score.mods)  # pyright: ignore[reportArgumentType]
    perf = rosu.Performance(
        mods=score.mods,
        lazer=True,
        accuracy=score.accuracy,
        combo=score.max_combo,
        large_tick_hits=score.nlarge_tick_hit or 0,
        slider_end_hits=score.nslider_tail_hit or 0,
        small_tick_hits=score.nsmall_tick_hit or 0,
        n_geki=score.ngeki,
        n_katu=score.nkatu,
        n300=score.n300,
        n100=score.n100,
        n50=score.n50,
        misses=score.nmiss,
    )
    attrs = perf.calculate(map)
    return attrs.pp


# https://osu.ppy.sh/wiki/Gameplay/Score/Total_score
def calculate_level_to_score(n: int) -> float:
    if n <= 100:
        return 5000 / 3 * (4 * n**3 - 3 * n**2 - n) + 1.25 * 1.8 ** (n - 60)
    else:
        return 26931190827 + 99999999999 * (n - 100)


# https://github.com/ppy/osu-queue-score-statistics/blob/4bdd479530408de73f3cdd95e097fe126772a65b/osu.Server.Queues.ScoreStatisticsProcessor/Processors/TotalScoreProcessor.cs#L70-L116
def calculate_score_to_level(total_score: int) -> float:
    to_next_level = [
        30000,
        100000,
        210000,
        360000,
        550000,
        780000,
        1050000,
        1360000,
        1710000,
        2100000,
        2530000,
        3000000,
        3510000,
        4060000,
        4650000,
        5280000,
        5950000,
        6660000,
        7410000,
        8200000,
        9030000,
        9900000,
        10810000,
        11760000,
        12750000,
        13780000,
        14850000,
        15960000,
        17110000,
        18300000,
        19530000,
        20800000,
        22110000,
        23460000,
        24850000,
        26280000,
        27750000,
        29260000,
        30810000,
        32400000,
        34030000,
        35700000,
        37410000,
        39160000,
        40950000,
        42780000,
        44650000,
        46560000,
        48510000,
        50500000,
        52530000,
        54600000,
        56710000,
        58860000,
        61050000,
        63280000,
        65550000,
        67860000,
        70210001,
        72600001,
        75030002,
        77500003,
        80010006,
        82560010,
        85150019,
        87780034,
        90450061,
        93160110,
        95910198,
        98700357,
        101530643,
        104401157,
        107312082,
        110263748,
        113256747,
        116292144,
        119371859,
        122499346,
        125680824,
        128927482,
        132259468,
        135713043,
        139353477,
        143298259,
        147758866,
        153115959,
        160054726,
        169808506,
        184597311,
        208417160,
        248460887,
        317675597,
        439366075,
        655480935,
        1041527682,
        1733419828,
        2975801691,
        5209033044,
        9225761479,
        99999999999,
        99999999999,
        99999999999,
        99999999999,
        99999999999,
        99999999999,
        99999999999,
        99999999999,
        99999999999,
        99999999999,
        99999999999,
        99999999999,
        99999999999,
        99999999999,
        99999999999,
        99999999999,
        99999999999,
        99999999999,
        99999999999,
        99999999999,
        99999999999,
        99999999999,
        99999999999,
        99999999999,
    ]

    remaining_score = total_score
    level = 0.0

    while remaining_score > 0:
        next_level_requirement = to_next_level[
            min(len(to_next_level) - 1, round(level))
        ]
        level += min(1, remaining_score / next_level_requirement)
        remaining_score -= next_level_requirement

    return level + 1


# https://osu.ppy.sh/wiki/Performance_points/Weighting_system
def calculate_pp_weight(index: int) -> float:
    return math.pow(0.95, index)


def calculate_weighted_pp(pp: float, index: int) -> float:
    return calculate_pp_weight(index) * pp if pp > 0 else 0.0


def calculate_weighted_acc(acc: float, index: int) -> float:
    return calculate_pp_weight(index) * acc if acc > 0 else 0.0
