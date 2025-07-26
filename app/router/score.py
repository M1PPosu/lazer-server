from __future__ import annotations

from app.database import (
    Beatmap,
    User as DBUser,
)
from app.database.beatmapset import Beatmapset
from app.database.score import Score, ScoreResp
from app.dependencies.database import get_db
from app.dependencies.user import get_current_user

from .api_router import router

from fastapi import Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import joinedload
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession


class BeatmapScores(BaseModel):
    scores: list[ScoreResp]
    userScore: ScoreResp | None = None


@router.get(
    "/beatmaps/{beatmap}/scores", tags=["beatmap"], response_model=BeatmapScores
)
async def get_beatmap_scores(
    beatmap: int,
    legacy_only: bool = Query(None),  # TODO:加入对这个参数的查询
    mode: str = Query(None),
    # mods: List[APIMod] = Query(None), # TODO:加入指定MOD的查询
    type: str = Query(None),
    current_user: DBUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if legacy_only:
        raise HTTPException(
            status_code=404, detail="this server only contains lazer scores"
        )

    all_scores = (
        await db.exec(
            select(Score).where(Score.beatmap_id == beatmap)
            # .where(Score.mods == mods if mods else True)
        )
    ).all()

    user_score = (
        await db.exec(
            select(Score)
            .options(
                joinedload(Score.beatmap)  # pyright: ignore[reportArgumentType]
                .joinedload(Beatmap.beatmapset)  # pyright: ignore[reportArgumentType]
                .selectinload(
                    Beatmapset.beatmaps  # pyright: ignore[reportArgumentType]
                )
            )
            .where(Score.beatmap_id == beatmap)
            .where(Score.user_id == current_user.id)
        )
    ).first()

    return BeatmapScores(
        scores=[ScoreResp.from_db(score) for score in all_scores],
        userScore=ScoreResp.from_db(user_score) if user_score else None,
    )


class BeatmapUserScore(BaseModel):
    position: int
    score: ScoreResp


@router.get(
    "/beatmaps/{beatmap}/scores/users/{user}",
    tags=["beatmap"],
    response_model=BeatmapUserScore,
)
async def get_user_beatmap_score(
    beatmap: int,
    user: int,
    legacy_only: bool = Query(None),
    mode: str = Query(None),
    mods: str = Query(None),  # TODO:添加mods筛选
    current_user: DBUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if legacy_only:
        raise HTTPException(
            status_code=404, detail="This server only contains non-legacy scores"
        )
    user_score = (
        await db.exec(
            select(Score)
            .options(
                joinedload(Score.beatmap)  # pyright: ignore[reportArgumentType]
                .joinedload(Beatmap.beatmapset)  # pyright: ignore[reportArgumentType]
                .selectinload(
                    Beatmapset.beatmaps  # pyright: ignore[reportArgumentType]
                )
            )
            .where(Score.gamemode == mode if mode is not None else True)
            .where(Score.beatmap_id == beatmap)
            .where(Score.user_id == user)
            .order_by(col(Score.classic_total_score).desc())
        )
    ).first()

    if not user_score:
        raise HTTPException(
            status_code=404, detail=f"Cannot find user {user}'s score on this beatmap"
        )
    else:
        return BeatmapUserScore(
            position=user_score.position if user_score.position is not None else 0,
            score=ScoreResp.from_db(user_score),
        )


@router.get(
    "/beatmaps/{beatmap}/scores/users/{user}/all",
    tags=["beatmap"],
    response_model=list[ScoreResp],
)
async def get_user_all_beatmap_scores(
    beatmap: int,
    user: int,
    legacy_only: bool = Query(None),
    ruleset: str = Query(None),
    current_user: DBUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if legacy_only:
        raise HTTPException(
            status_code=404, detail="This server only contains non-legacy scores"
        )
    all_user_scores = (
        await db.exec(
            select(Score)
            .options(
                joinedload(Score.beatmap)  # pyright: ignore[reportArgumentType]
                .joinedload(Beatmap.beatmapset)  # pyright: ignore[reportArgumentType]
                .selectinload(
                    Beatmapset.beatmaps  # pyright: ignore[reportArgumentType]
                )
            )
            .where(Score.gamemode == ruleset if ruleset is not None else True)
            .where(Score.beatmap_id == beatmap)
            .where(Score.user_id == user)
            .order_by(col(Score.classic_total_score).desc())
        )
    ).all()

    return [ScoreResp.from_db(score) for score in all_user_scores]
