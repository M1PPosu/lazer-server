from __future__ import annotations

from datetime import datetime
from typing import Literal

from app.database.lazer_user import User
from app.database.statistics import UserStatistics, UserStatisticsResp
from app.dependencies.database import get_db
from app.models.score import GameMode

from .router import AllStrModel, router

from fastapi import Depends, HTTPException, Query
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession


class V1User(AllStrModel):
    user_id: int
    username: str
    join_date: datetime
    count300: int
    count100: int
    count50: int
    playcount: int
    ranked_score: int
    total_score: int
    pp_rank: int
    level: float
    pp_raw: float
    accuracy: float
    count_rank_ss: int
    count_rank_ssh: int
    count_rank_s: int
    count_rank_sh: int
    count_rank_a: int
    country: str
    total_seconds_played: int
    pp_country_rank: int
    events: list[dict]

    @classmethod
    async def from_db(
        cls, session: AsyncSession, db_user: User, ruleset: GameMode | None = None
    ) -> "V1User":
        ruleset = ruleset or db_user.playmode
        current_statistics: UserStatistics | None = None
        for i in await db_user.awaitable_attrs.statistics:
            if i.mode == ruleset:
                current_statistics = i
                break
        if current_statistics:
            statistics = await UserStatisticsResp.from_db(
                current_statistics, session, db_user.country_code
            )
        else:
            statistics = None
        return cls(
            user_id=db_user.id,
            username=db_user.username,
            join_date=db_user.join_date,
            count300=statistics.count_300 if statistics else 0,
            count100=statistics.count_100 if statistics else 0,
            count50=statistics.count_50 if statistics else 0,
            playcount=statistics.play_count if statistics else 0,
            ranked_score=statistics.ranked_score if statistics else 0,
            total_score=statistics.total_score if statistics else 0,
            pp_rank=statistics.global_rank
            if statistics and statistics.global_rank
            else 0,
            level=current_statistics.level_current if current_statistics else 0,
            pp_raw=statistics.pp if statistics else 0.0,
            accuracy=statistics.hit_accuracy if statistics else 0,
            count_rank_ss=current_statistics.grade_ss if current_statistics else 0,
            count_rank_ssh=current_statistics.grade_ssh if current_statistics else 0,
            count_rank_s=current_statistics.grade_s if current_statistics else 0,
            count_rank_sh=current_statistics.grade_sh if current_statistics else 0,
            count_rank_a=current_statistics.grade_a if current_statistics else 0,
            country=db_user.country_code,
            total_seconds_played=statistics.play_time if statistics else 0,
            pp_country_rank=statistics.country_rank
            if statistics and statistics.country_rank
            else 0,
            events=[],  # TODO
        )


@router.get(
    "/get_user",
    response_model=list[V1User],
    name="获取用户信息",
    description="获取指定用户的信息。",
)
async def get_user(
    user: str = Query(..., alias="u", description="用户"),
    ruleset_id: int | None = Query(None, alias="m", description="Ruleset ID", ge=0),
    type: Literal["string", "id"] | None = Query(
        None, description="用户类型：string 用户名称 / id 用户 ID"
    ),
    event_days: int = Query(
        default=1, ge=1, le=31, description="从现在起所有事件的最大天数"
    ),
    session: AsyncSession = Depends(get_db),
):
    db_user = (
        await session.exec(
            select(User).where(
                User.id == user
                if type == "id" or user.isdigit()
                else User.username == user,
            )
        )
    ).first()
    if not db_user:
        return []
    try:
        return [
            await V1User.from_db(
                session,
                db_user,
                GameMode.from_int_extra(ruleset_id) if ruleset_id else None,
            )
        ]
    except KeyError:
        raise HTTPException(400, "Invalid request")
