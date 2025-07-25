from __future__ import annotations

from app.database import (
    Beatmap,
    BeatmapResp,
    User as DBUser,
)
from app.dependencies.database import get_db
from app.dependencies.user import get_current_user

from .api_router import router

from fastapi import Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, col, select


@router.get("/beatmaps/{bid}", tags=["beatmap"], response_model=BeatmapResp)
async def get_beatmap(
    bid: int,
    current_user: DBUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    beatmap = db.exec(select(Beatmap).where(Beatmap.id == bid)).first()
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
    db: Session = Depends(get_db),
):
    if not b_ids:
        # select 50 beatmaps by last_updated
        beatmaps = db.exec(
            select(Beatmap).order_by(col(Beatmap.last_updated).desc()).limit(50)
        ).all()
    else:
        beatmaps = db.exec(
            select(Beatmap).where(col(Beatmap.id).in_(b_ids)).limit(50)
        ).all()

    return BatchGetResp(beatmaps=[BeatmapResp.from_db(bm) for bm in beatmaps])
