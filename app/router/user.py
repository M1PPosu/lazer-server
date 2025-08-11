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

from .api_router import router

from fastapi import Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import exists, false, select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel.sql.expression import col


class BatchUserResponse(BaseModel):
    users: list[UserResp]


@router.get("/users", response_model=BatchUserResponse)
@router.get("/users/lookup", response_model=BatchUserResponse)
@router.get("/users/lookup/", response_model=BatchUserResponse)
async def get_users(
    user_ids: list[int] = Query(default_factory=list, alias="ids[]"),
    include_variant_statistics: bool = Query(default=False),  # TODO: future use
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


@router.get("/users/{user}/{ruleset}", response_model=UserResp)
@router.get("/users/{user}/", response_model=UserResp)
@router.get("/users/{user}", response_model=UserResp)
async def get_user_info(
    user: str,
    ruleset: GameMode | None = None,
    session: AsyncSession = Depends(get_db),
):
    searched_user = (
        await session.exec(
            select(User).where(
                User.id == int(user)
                if user.isdigit()
                else User.username == user.removeprefix("@")
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


@router.get(
    "/users/{user_id}/beatmapsets/{type}",
    response_model=list[BeatmapsetResp | BeatmapPlaycountsResp],
)
async def get_user_beatmapsets(
    user_id: int,
    type: BeatmapsetType,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
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
                favourite.beatmapset, session=session, user=current_user
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


@router.get("/users/{user}/scores/{type}", response_model=list[ScoreResp])
async def get_user_scores(
    user: int,
    type: Literal["best", "recent", "firsts", "pinned"],
    legacy_only: bool = Query(False),
    include_fails: bool = Query(False),
    mode: GameMode | None = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
):
    db_user = await session.get(User, user)
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
