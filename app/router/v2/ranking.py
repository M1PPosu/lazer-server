from __future__ import annotations

from typing import Literal

from app.database import User
from app.database.statistics import UserStatistics, UserStatisticsResp
from app.dependencies import get_current_user
from app.dependencies.database import get_db
from app.models.score import GameMode

from .router import router

from fastapi import Depends, Path, Query, Security
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession


@router.get(
    "/rankings/{ruleset}/{type}",
    response_model=list[UserStatisticsResp],
    name="获取排行榜",
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
    wheres = [col(UserStatistics.mode) == ruleset]
    if type == "performance":
        order_by = col(UserStatistics.pp).desc()
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
    return [
        await UserStatisticsResp.from_db(statistics, session, None)
        for statistics in statistics_list
    ]
