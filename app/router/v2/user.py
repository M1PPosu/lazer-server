from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal

from app.database import (
    BeatmapPlaycounts,
    BeatmapPlaycountsResp,
    BeatmapsetResp,
    User,
    UserResp,
)
from app.database.lazer_user import SEARCH_INCLUDED
from app.database.pp_best_score import PPBestScore
from app.database.score import Score, ScoreResp
from app.dependencies.database import get_db
from app.dependencies.user import get_current_user
from app.models.score import GameMode
from app.models.user import BeatmapsetType

from .router import router

from fastapi import Depends, HTTPException, Path, Query, Security
from pydantic import BaseModel
from sqlmodel import exists, false, select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel.sql.expression import col


class BatchUserResponse(BaseModel):
    users: list[UserResp]


@router.get(
    "/users",
    response_model=BatchUserResponse,
    name="批量获取用户信息",
    description="通过用户 ID 列表批量获取用户信息。",
    tags=["用户"],
)
@router.get("/users/lookup", response_model=BatchUserResponse, include_in_schema=False)
@router.get("/users/lookup/", response_model=BatchUserResponse, include_in_schema=False)
async def get_users(
    user_ids: list[int] = Query(
        default_factory=list, alias="ids[]", description="要查询的用户 ID 列表"
    ),
    # current_user: User = Security(get_current_user, scopes=["public"]),
    include_variant_statistics: bool = Query(
        default=False, description="是否包含各模式的统计信息"
    ),  # TODO: future use
    session: AsyncSession = Depends(get_db),
):
    if user_ids:
        searched_users = (
            await session.exec(select(User).limit(50).where(col(User.id).in_(user_ids)))
        ).all()
    else:
        searched_users = (await session.exec(select(User).limit(50))).all()
    return BatchUserResponse(
        users=[
            await UserResp.from_db(
                searched_user,
                session,
                include=SEARCH_INCLUDED,
            )
            for searched_user in searched_users
        ]
    )


@router.get(
    "/users/{user_id}/{ruleset}",
    response_model=UserResp,
    name="获取用户信息(指定ruleset)",
    description="通过用户 ID 或用户名获取单个用户的详细信息，并指定特定 ruleset。",
    tags=["用户"],
)
async def get_user_info_ruleset(
    user_id: str = Path(description="用户 ID 或用户名"),
    ruleset: GameMode | None = Path(description="指定 ruleset"),
    session: AsyncSession = Depends(get_db),
    # current_user: User = Security(get_current_user, scopes=["public"]),
):
    searched_user = (
        await session.exec(
            select(User).where(
                User.id == int(user_id)
                if user_id.isdigit()
                else User.username == user_id.removeprefix("@")
            )
        )
    ).first()
    if not searched_user:
        raise HTTPException(404, detail="User not found")
    return await UserResp.from_db(
        searched_user,
        session,
        include=SEARCH_INCLUDED,
        ruleset=ruleset,
    )


@router.get("/users/{user_id}/", response_model=UserResp, include_in_schema=False)
@router.get(
    "/users/{user_id}",
    response_model=UserResp,
    name="获取用户信息",
    description="通过用户 ID 或用户名获取单个用户的详细信息。",
    tags=["用户"],
)
async def get_user_info(
    user_id: str = Path(description="用户 ID 或用户名"),
    session: AsyncSession = Depends(get_db),
    # current_user: User = Security(get_current_user, scopes=["public"]),
):
    searched_user = (
        await session.exec(
            select(User).where(
                User.id == int(user_id)
                if user_id.isdigit()
                else User.username == user_id.removeprefix("@")
            )
        )
    ).first()
    if not searched_user:
        raise HTTPException(404, detail="User not found")
    return await UserResp.from_db(
        searched_user,
        session,
        include=SEARCH_INCLUDED,
    )


@router.get(
    "/users/{user_id}/beatmapsets/{type}",
    response_model=list[BeatmapsetResp | BeatmapPlaycountsResp],
    name="获取用户谱面集列表",
    description="获取指定用户特定类型的谱面集列表，如最常游玩、收藏等。",
    tags=["用户"],
)
async def get_user_beatmapsets(
    user_id: int = Path(description="用户 ID"),
    type: BeatmapsetType = Path(description="谱面集类型"),
    current_user: User = Security(get_current_user, scopes=["public"]),
    session: AsyncSession = Depends(get_db),
    limit: int = Query(100, ge=1, le=1000, description="返回条数 (1-1000)"),
    offset: int = Query(0, ge=0, description="偏移量"),
):
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(404, detail="User not found")

    if type in {
        BeatmapsetType.GRAVEYARD,
        BeatmapsetType.GUEST,
        BeatmapsetType.LOVED,
        BeatmapsetType.NOMINATED,
        BeatmapsetType.PENDING,
        BeatmapsetType.RANKED,
    }:
        # TODO: mapping, modding
        resp = []

    elif type == BeatmapsetType.FAVOURITE:
        user = await session.get(User, user_id)
        if not user:
            raise HTTPException(404, detail="User not found")
        favourites = await user.awaitable_attrs.favourite_beatmapsets
        resp = [
            await BeatmapsetResp.from_db(
                favourite.beatmapset, session=session, user=user
            )
            for favourite in favourites
        ]

    elif type == BeatmapsetType.MOST_PLAYED:
        most_played = await session.exec(
            select(BeatmapPlaycounts)
            .where(BeatmapPlaycounts.user_id == user_id)
            .order_by(col(BeatmapPlaycounts.playcount).desc())
            .limit(limit)
            .offset(offset)
        )
        resp = [
            await BeatmapPlaycountsResp.from_db(most_played_beatmap)
            for most_played_beatmap in most_played
        ]
    else:
        raise HTTPException(400, detail="Invalid beatmapset type")

    return resp


@router.get(
    "/users/{user_id}/scores/{type}",
    response_model=list[ScoreResp],
    name="获取用户成绩列表",
    description="获取用户特定类型的成绩列表，如最好成绩、最近成绩等。",
    tags=["用户"],
)
async def get_user_scores(
    user_id: int = Path(description="用户 ID"),
    type: Literal["best", "recent", "firsts", "pinned"] = Path(
        description=(
            "成绩类型: best 最好成绩 / recent 最近 24h 游玩成绩"
            " / firsts 第一名成绩 / pinned 置顶成绩"
        )
    ),
    legacy_only: bool = Query(False, description="是否只查询 Stable 成绩"),
    include_fails: bool = Query(False, description="是否包含失败的成绩"),
    mode: GameMode | None = Query(
        None, description="指定 ruleset (可选，默认为用户主模式)"
    ),
    limit: int = Query(100, ge=1, le=1000, description="返回条数 (1-1000)"),
    offset: int = Query(0, ge=0, description="偏移量"),
    session: AsyncSession = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=["public"]),
):
    db_user = await session.get(User, user_id)
    if not db_user:
        raise HTTPException(404, detail="User not found")

    gamemode = mode or db_user.playmode
    order_by = None
    where_clause = (col(Score.user_id) == db_user.id) & (
        col(Score.gamemode) == gamemode
    )
    if not include_fails:
        where_clause &= col(Score.passed).is_(True)
    if type == "pinned":
        where_clause &= Score.pinned_order > 0
        order_by = col(Score.pinned_order).asc()
    elif type == "best":
        where_clause &= exists().where(col(PPBestScore.score_id) == Score.id)
        order_by = col(Score.pp).desc()
    elif type == "recent":
        where_clause &= Score.ended_at > datetime.now(UTC) - timedelta(hours=24)
        order_by = col(Score.ended_at).desc()
    elif type == "firsts":
        # TODO
        where_clause &= false()

    scores = (
        await session.exec(
            select(Score)
            .where(where_clause)
            .order_by(order_by)
            .limit(limit)
            .offset(offset)
        )
    ).all()
    if not scores:
        return []
    return [
        await ScoreResp.from_db(
            session,
            score,
        )
        for score in scores
    ]
