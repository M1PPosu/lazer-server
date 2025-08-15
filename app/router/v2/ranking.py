from __future__ import annotations

from typing import Literal

from app.database import User
from app.database.statistics import UserStatistics, UserStatisticsResp
from app.dependencies import get_current_user
from app.dependencies.database import get_db
from app.models.score import GameMode

from .router import router

from fastapi import Depends, Path, Query, Security
from pydantic import BaseModel
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession


class CountryStatistics(BaseModel):
    code: str
    active_users: int
    play_count: int
    ranked_score: int
    performance: int


class CountryResponse(BaseModel):
    ranking: list[CountryStatistics]


@router.get(
    "/rankings/{ruleset}/country",
    response_model=CountryResponse,
    name="获取地区排行榜",
    description="获取在指定模式下的地区排行榜",
    tags=["排行榜"],
)
async def get_country_ranking(
    ruleset: GameMode = Path(..., description="指定 ruleset"),
    page: int = Query(1, ge=1, description="页码"),  # TODO
    current_user: User = Security(get_current_user, scopes=["public"]),
    session: AsyncSession = Depends(get_db),
):
    response = CountryResponse(ranking=[])
    countries = (await session.exec(select(User.country_code).distinct())).all()
    for country in countries:
        statistics = (
            await session.exec(
                select(UserStatistics).where(
                    UserStatistics.mode == ruleset,
                    UserStatistics.pp > 0,
                    col(UserStatistics.user).has(country_code=country),
                    col(UserStatistics.user).has(is_active=True),
                )
            )
        ).all()
        pp = 0
        country_stats = CountryStatistics(
            code=country,
            active_users=0,
            play_count=0,
            ranked_score=0,
            performance=0,
        )
        for stat in statistics:
            country_stats.active_users += 1
            country_stats.play_count += stat.play_count
            country_stats.ranked_score += stat.ranked_score
            pp += stat.pp
        country_stats.performance = round(pp)
        response.ranking.append(country_stats)
    response.ranking.sort(key=lambda x: x.performance, reverse=True)
    return response


class TopUsersResponse(BaseModel):
    ranking: list[UserStatisticsResp]


@router.get(
    "/rankings/{ruleset}/{type}",
    response_model=TopUsersResponse,
    name="获取用户排行榜",
    description="获取在指定模式下的用户排行榜",
    tags=["排行榜"],
)
async def get_user_ranking(
    ruleset: GameMode = Path(..., description="指定 ruleset"),
    type: Literal["performance", "score"] = Path(
        ..., description="排名类型：performance 表现分 / score 计分成绩总分"
    ),
    country: str | None = Query(None, description="国家代码"),
    page: int = Query(1, ge=1, description="页码"),
    current_user: User = Security(get_current_user, scopes=["public"]),
    session: AsyncSession = Depends(get_db),
):
    wheres = [
        col(UserStatistics.mode) == ruleset,
        col(UserStatistics.pp) > 0,
        col(UserStatistics.is_ranked).is_(True),
    ]
    include = ["user"]
    if type == "performance":
        order_by = col(UserStatistics.pp).desc()
        include.append("rank_change_since_30_days")
    else:
        order_by = col(UserStatistics.ranked_score).desc()
    if country:
        wheres.append(col(UserStatistics.user).has(country_code=country.upper()))
    statistics_list = await session.exec(
        select(UserStatistics)
        .where(*wheres)
        .order_by(order_by)
        .limit(50)
        .offset(50 * (page - 1))
    )
    resp = TopUsersResponse(
        ranking=[
            await UserStatisticsResp.from_db(statistics, session, None, include)
            for statistics in statistics_list
        ]
    )
    return resp
