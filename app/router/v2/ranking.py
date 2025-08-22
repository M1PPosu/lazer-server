from __future__ import annotations

from typing import Literal

from app.config import settings
from app.database import User
from app.database.statistics import UserStatistics, UserStatisticsResp
from app.dependencies import get_current_user
from app.dependencies.database import Database, get_redis
from app.models.score import GameMode
from app.service.ranking_cache_service import get_ranking_cache_service

from .router import router

from fastapi import BackgroundTasks, Path, Query, Security
from pydantic import BaseModel
from sqlmodel import col, select


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
    session: Database,
    background_tasks: BackgroundTasks,
    ruleset: GameMode = Path(..., description="指定 ruleset"),
    page: int = Query(1, ge=1, description="页码"),  # TODO
    current_user: User = Security(get_current_user, scopes=["public"]),
):
    # 获取 Redis 连接和缓存服务
    redis = get_redis()
    cache_service = get_ranking_cache_service(redis)

    # 尝试从缓存获取数据
    cached_data = await cache_service.get_cached_country_ranking(ruleset, page)

    if cached_data:
        # 从缓存返回数据
        return CountryResponse(ranking=[CountryStatistics.model_validate(item) for item in cached_data])

    # 缓存未命中，从数据库查询
    response = CountryResponse(ranking=[])
    countries = (await session.exec(select(User.country_code).distinct())).all()

    for country in countries:
        if not country:  # 跳过空的国家代码
            continue

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

        if not statistics:  # 跳过没有数据的国家
            continue

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

    # 分页处理
    page_size = 50
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size

    # 获取当前页的数据
    current_page_data = response.ranking[start_idx:end_idx]

    # 异步缓存数据（不等待完成）
    cache_data = [item.model_dump() for item in current_page_data]

    # 创建后台任务来缓存数据
    background_tasks.add_task(
        cache_service.cache_country_ranking,
        ruleset,
        cache_data,
        page,
        ttl=settings.ranking_cache_expire_minutes * 60,
    )

    # 返回当前页的结果
    response.ranking = current_page_data
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
    session: Database,
    background_tasks: BackgroundTasks,
    ruleset: GameMode = Path(..., description="指定 ruleset"),
    type: Literal["performance", "score"] = Path(..., description="排名类型：performance 表现分 / score 计分成绩总分"),
    country: str | None = Query(None, description="国家代码"),
    page: int = Query(1, ge=1, description="页码"),
    current_user: User = Security(get_current_user, scopes=["public"]),
):
    # 获取 Redis 连接和缓存服务
    redis = get_redis()
    cache_service = get_ranking_cache_service(redis)

    # 尝试从缓存获取数据
    cached_data = await cache_service.get_cached_ranking(ruleset, type, country, page)

    if cached_data:
        # 从缓存返回数据
        return TopUsersResponse(ranking=[UserStatisticsResp.model_validate(item) for item in cached_data])

    # 缓存未命中，从数据库查询
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
        select(UserStatistics).where(*wheres).order_by(order_by).limit(50).offset(50 * (page - 1))
    )

    # 转换为响应格式
    ranking_data = []
    for statistics in statistics_list:
        user_stats_resp = await UserStatisticsResp.from_db(statistics, session, None, include)
        ranking_data.append(user_stats_resp)

    # 异步缓存数据（不等待完成）
    # 使用配置文件中的TTL设置
    cache_data = [item.model_dump() for item in ranking_data]
    # 创建后台任务来缓存数据

    background_tasks.add_task(
        cache_service.cache_ranking,
        ruleset,
        type,
        cache_data,
        country,
        page,
        ttl=settings.ranking_cache_expire_minutes * 60,
    )

    resp = TopUsersResponse(ranking=ranking_data)
    return resp


# @router.post(
#     "/rankings/cache/refresh",
#     name="刷新排行榜缓存",
#     description="手动刷新排行榜缓存（管理员功能）",
#     tags=["排行榜", "管理"],
# )
# async def refresh_ranking_cache(
#     session: Database,
#     ruleset: GameMode | None = Query(None, description="指定要刷新的游戏模式，不指定则刷新所有"),
#     type: Literal["performance", "score"] | None = Query(None, description="指定要刷新的排名类型，不指定则刷新所有"),
#     country: str | None = Query(None, description="指定要刷新的国家，不指定则刷新所有"),
#     include_country_ranking: bool = Query(True, description="是否包含地区排行榜"),
#     current_user: User = Security(get_current_user, scopes=["admin"]),  # 需要管理员权限
# ):
#     redis = get_redis()
#     cache_service = get_ranking_cache_service(redis)

#     if ruleset and type:
#         # 刷新特定的用户排行榜
#         await cache_service.refresh_ranking_cache(session, ruleset, type, country)
#         message = f"Refreshed ranking cache for {ruleset}:{type}" + (f" in {country}" if country else "")

#         # 如果请求刷新地区排行榜
#         if include_country_ranking and not country:  # 地区排行榜不依赖于国家参数
#             await cache_service.refresh_country_ranking_cache(session, ruleset)
#             message += f" and country ranking for {ruleset}"

#         return {"message": message}
#     elif ruleset:
#         # 刷新特定游戏模式的所有排行榜
#         ranking_types: list[Literal["performance", "score"]] = ["performance", "score"]
#         for ranking_type in ranking_types:
#             await cache_service.refresh_ranking_cache(session, ruleset, ranking_type, country)

#         if include_country_ranking:
#             await cache_service.refresh_country_ranking_cache(session, ruleset)

#         return {"message": f"Refreshed all ranking caches for {ruleset}"}
#     else:
#         # 刷新所有排行榜
#         await cache_service.refresh_all_rankings(session)
#         return {"message": "Refreshed all ranking caches"}


# @router.post(
#     "/rankings/{ruleset}/country/cache/refresh",
#     name="刷新地区排行榜缓存",
#     description="手动刷新地区排行榜缓存（管理员功能）",
#     tags=["排行榜", "管理"],
# )
# async def refresh_country_ranking_cache(
#     session: Database,
#     ruleset: GameMode = Path(..., description="指定要刷新的游戏模式"),
#     current_user: User = Security(get_current_user, scopes=["admin"]),  # 需要管理员权限
# ):
#     redis = get_redis()
#     cache_service = get_ranking_cache_service(redis)

#     await cache_service.refresh_country_ranking_cache(session, ruleset)
#     return {"message": f"Refreshed country ranking cache for {ruleset}"}


# @router.delete(
#     "/rankings/cache",
#     name="清除排行榜缓存",
#     description="清除排行榜缓存（管理员功能）",
#     tags=["排行榜", "管理"],
# )
# async def clear_ranking_cache(
#     ruleset: GameMode | None = Query(None, description="指定要清除的游戏模式，不指定则清除所有"),
#     type: Literal["performance", "score"] | None = Query(None, description="指定要清除的排名类型，不指定则清除所有"),
#     country: str | None = Query(None, description="指定要清除的国家，不指定则清除所有"),
#     include_country_ranking: bool = Query(True, description="是否包含地区排行榜"),
#     current_user: User = Security(get_current_user, scopes=["admin"]),  # 需要管理员权限
# ):
#     redis = get_redis()
#     cache_service = get_ranking_cache_service(redis)

#     await cache_service.invalidate_cache(ruleset, type, country, include_country_ranking)

#     if ruleset and type:
#         message = f"Cleared ranking cache for {ruleset}:{type}" + (f" in {country}" if country else "")
#         if include_country_ranking:
#             message += " and country ranking"
#         return {"message": message}
#     else:
#         message = "Cleared all ranking caches"
#         if include_country_ranking:
#             message += " including country rankings"
#         return {"message": message}


# @router.delete(
#     "/rankings/{ruleset}/country/cache",
#     name="清除地区排行榜缓存",
#     description="清除地区排行榜缓存（管理员功能）",
#     tags=["排行榜", "管理"],
# )
# async def clear_country_ranking_cache(
#     ruleset: GameMode | None = Query(None, description="指定要清除的游戏模式，不指定则清除所有"),
#     current_user: User = Security(get_current_user, scopes=["admin"]),  # 需要管理员权限
# ):
#     redis = get_redis()
#     cache_service = get_ranking_cache_service(redis)

#     await cache_service.invalidate_country_cache(ruleset)

#     if ruleset:
#         return {"message": f"Cleared country ranking cache for {ruleset}"}
#     else:
#         return {"message": "Cleared all country ranking caches"}


# @router.get(
#     "/rankings/cache/stats",
#     name="获取排行榜缓存统计",
#     description="获取排行榜缓存统计信息（管理员功能）",
#     tags=["排行榜", "管理"],
# )
# async def get_ranking_cache_stats(
#     current_user: User = Security(get_current_user, scopes=["admin"]),  # 需要管理员权限
# ):
#     redis = get_redis()
#     cache_service = get_ranking_cache_service(redis)

#     stats = await cache_service.get_cache_stats()
#     return stats
