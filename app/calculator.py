from __future__ import annotations

import math
from typing import TYPE_CHECKING

from app.models.beatmap import BeatmapAttributes
from app.models.mods import APIMod
from app.models.score import GameMode

import rosu_pp_py as rosu

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
    if map.is_suspicious():
        return 0.0
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
        hitresult_priority=rosu.HitResultPriority.Fastest,
    )
    attrs = perf.calculate(map)
    return attrs.pp


# https://osu.ppy.sh/wiki/Gameplay/Score/Total_score
def calculate_level_to_score(level: int) -> float:
    if level <= 100:
        # 55 = 4^3 - 3^2
        return 5000 / 3 * (55 - level) + 1.25 * math.pow(1.8, level - 60)
    else:
        return 26_931_190_827 + 99_999_999_999 * (level - 100)


def calculate_score_to_level(score: float) -> int:
    if score < 5000:
        return int(55 - (3 * score / 5000))  # 55 = 4^3 - 3^2
    elif score < 26_931_190_827:
        return int(60 + math.log(score / 1.25, 1.8))
    else:
        return int((score - 26_931_190_827) / 99_999_999_999 + 100)


# https://osu.ppy.sh/wiki/Performance_points/Weighting_system
def calculate_pp_weight(index: int) -> float:
    return math.pow(0.95, index)


def calculate_weighted_pp(pp: float, index: int) -> float:
    return calculate_pp_weight(index) * pp if pp > 0 else 0.0


def calculate_weighted_acc(acc: float, index: int) -> float:
    return calculate_pp_weight(index) * acc if acc > 0 else 0.0
