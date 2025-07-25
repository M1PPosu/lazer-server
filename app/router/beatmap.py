from __future__ import annotations

from app.database import (
    Beatmap,
    BeatmapResp,
    User as DBUser,
)
from app.database.score import Score, ScoreResp, APIMod
from app.database.beatmapset import Beatmapset
from app.dependencies.database import get_db
from app.dependencies.user import get_current_user

from .api_router import router

from fastapi import Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import joinedload
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession


@router.get("/beatmaps/{bid}", tags=["beatmap"], response_model=BeatmapResp)
async def get_beatmap(
    bid: int,
    current_user: DBUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    beatmap = (
        await db.exec(
            select(Beatmap)
            .options(
                joinedload(Beatmap.beatmapset).selectinload(Beatmapset.beatmaps))  # pyright: ignore[reportArgumentType]
            .where(Beatmap.id == bid)
        )
    ).first()
    if not beatmap:
        raise HTTPException(status_code=404, detail="Beatmap not found")
    return BeatmapResp.from_db(beatmap)


class BatchGetResp(BaseModel):
    beatmaps: list[BeatmapResp]


@router.get("/beatmaps", tags=["beatmap"], response_model=BatchGetResp)
@router.get("/beatmaps/", tags=["beatmap"], response_model=BatchGetResp)
async def batch_get_beatmaps(
    b_ids: list[int] = Query(alias="id", default_factory=list),
    current_user: DBUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not b_ids:
        # select 50 beatmaps by last_updated
        beatmaps = (
            await db.exec(
                select(Beatmap)
                .options(
                    joinedload(Beatmap.beatmapset).selectinload(Beatmapset.beatmaps)  # pyright: ignore[reportArgumentType]
                )
                .order_by(col(Beatmap.last_updated).desc())
                .limit(50)
            )
        ).all()
    else:
        beatmaps = (
            await db.exec(
                select(Beatmap)
                .options(
                    joinedload(Beatmap.beatmapset).selectinload(Beatmapset.beatmaps)  # pyright: ignore[reportArgumentType]
                )
                .where(col(Beatmap.id).in_(b_ids))
                .limit(50)
            )
        ).all()

    return BatchGetResp(beatmaps=[BeatmapResp.from_db(bm) for bm in beatmaps])


class BeatmapScores(BaseModel):
    scores: list[ScoreResp]
    userScore: ScoreResp | None


@router.get(
    "/beatmaps/{beatmap}/scores", tags=["beatmapset"], response_model=BeatmapScores
)
async def get_beatmapset_scores(
    beatmap: int,
    legacy_only: bool = Query(None),  # TODO:加入对这个参数的查询
    mode: str = Query(None),
    mods: list[APIMod] = Query(None),
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
            select(Score)
            .where(Score.beatmap_id == beatmap)
            .where(Score.mods == APIMod if mods else True)
        )
    ).all()

    user_score = (
        await db.exec(
            select(Score)
            .where(Score.beatmap_id == beatmap)
            .where(Score.user_id == current_user.id)
        )
    ).first()

    return BeatmapScores(
        scores=[ScoreResp.from_db(score) for score in all_scores],
        userScore=ScoreResp.from_db(user_score) if user_score else None,
    )
