from __future__ import annotations

import asyncio
import math

from app.calculator import (
    calculate_pp,
    calculate_weighted_acc,
    calculate_weighted_pp,
    clamp,
)
from app.config import settings
from app.database import UserStatistics
from app.database.beatmap import Beatmap
from app.database.pp_best_score import PPBestScore
from app.database.score import Score
from app.dependencies.database import engine, get_redis
from app.dependencies.fetcher import get_fetcher
from app.fetcher import Fetcher
from app.log import logger
from app.models.mods import mods_can_get_pp
from app.models.score import MODE_TO_INT, GameMode

from httpx import HTTPError
from redis.asyncio import Redis
from sqlmodel import col, delete, select
from sqlmodel.ext.asyncio.session import AsyncSession


async def recalculate_all_players_pp():
    async with AsyncSession(engine, autoflush=False) as session:
        fetcher = await get_fetcher()
        redis = get_redis()
        for mode in GameMode:
            await session.execute(
                delete(PPBestScore).where(col(PPBestScore.gamemode) == mode)
            )
            logger.info(f"Recalculating PP for mode: {mode}")
            statistics_list = (
                await session.exec(
                    select(UserStatistics).where(UserStatistics.mode == mode)
                )
            ).all()
            await asyncio.gather(
                *[
                    _recalculate_pp(statistics, session, fetcher, redis)
                    for statistics in statistics_list
                ]
            )
            await session.commit()
            logger.success(
                f"Recalculated PP for mode: {mode}, total: {len(statistics_list)}"
            )


async def _recalculate_pp(
    statistics: UserStatistics, session: AsyncSession, fetcher: Fetcher, redis: Redis
):
    scores = (
        await session.exec(
            select(Score).where(
                Score.user_id == statistics.user_id,
                Score.gamemode == statistics.mode,
                col(Score.passed).is_(True),
            )
        )
    ).all()
    score_list: list[tuple[float, float]] = []
    prev: dict[int, PPBestScore] = {}
    for score in scores:
        time = 10
        beatmap_id = score.beatmap_id
        while time > 0:
            try:
                db_beatmap = await Beatmap.get_or_fetch(
                    session, fetcher, bid=beatmap_id
                )
            except HTTPError:
                time -= 1
                await asyncio.sleep(2)
                continue
            ranked = db_beatmap.beatmap_status.has_pp() | settings.enable_all_beatmap_pp
            if not ranked or not mods_can_get_pp(
                MODE_TO_INT[score.gamemode], score.mods
            ):
                score.pp = 0
                break
            try:
                beatmap_raw = await fetcher.get_or_fetch_beatmap_raw(redis, beatmap_id)
                pp = await asyncio.get_event_loop().run_in_executor(
                    None, calculate_pp, score, beatmap_raw
                )
                score.pp = pp
                if score.beatmap_id not in prev or prev[score.beatmap_id].pp < pp:
                    best_score = PPBestScore(
                        user_id=statistics.user_id,
                        beatmap_id=beatmap_id,
                        acc=score.accuracy,
                        score_id=score.id,
                        pp=pp,
                        gamemode=score.gamemode,
                    )
                    prev[score.beatmap_id] = best_score
                score_list.append((score.pp, score.accuracy))
                break
            except HTTPError:
                time -= 1
                await asyncio.sleep(2)
                continue
        if time <= 0:
            logger.error(f"Failed to fetch beatmap {beatmap_id} after 10 attempts")
            score.pp = 0
    # according to pp desc
    score_list.sort(key=lambda x: x[0], reverse=True)
    pp_sum = 0
    acc_sum = 0
    for i, s in enumerate(score_list):
        pp_sum += calculate_weighted_pp(s[0], i)
        acc_sum += calculate_weighted_acc(s[1], i)
    if len(score_list):
        # https://github.com/ppy/osu-queue-score-statistics/blob/c538ae/osu.Server.Queues.ScoreStatisticsProcessor/Helpers/UserTotalPerformanceAggregateHelper.cs#L41-L45
        acc_sum *= 100 / (20 * (1 - math.pow(0.95, len(score_list))))
    acc_sum = clamp(acc_sum, 0.0, 100.0)
    statistics.pp = pp_sum
    statistics.hit_accuracy = acc_sum
    for best_score in prev.values():
        session.add(best_score)
