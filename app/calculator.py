from __future__ import annotations

from app.database.score import Score
from app.models.beatmap import BeatmapAttributes
from app.models.mods import APIMod
from app.models.score import GameMode

import rosu_pp_py as rosu


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
    score: Score,
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
