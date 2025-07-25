from __future__ import annotations

from app.database import (
    Beatmap,
    BeatmapResp,
    User as DBUser,
)
from app.dependencies.database import get_db
from app.dependencies.user import get_current_user

from .api_router import router

from fastapi import Depends, HTTPException
from sqlmodel import Session, select


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
