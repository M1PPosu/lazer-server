from __future__ import annotations

from app.database import (
    Beatmapset,
    BeatmapsetResp,
    User as DBUser,
)
from app.dependencies.database import get_db
from app.dependencies.user import get_current_user

from .api_router import router

from fastapi import Depends, HTTPException
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession


@router.get("/beatmapsets/{sid}", tags=["beatmapset"], response_model=BeatmapsetResp)
async def get_beatmapset(
    sid: int,
    current_user: DBUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    beatmapset = (
        await db.exec(
            select(Beatmapset)
            .options(selectinload(Beatmapset.beatmaps))  # pyright: ignore[reportArgumentType]
            .where(Beatmapset.id == sid)
        )
    ).first()
    if not beatmapset:
        raise HTTPException(status_code=404, detail="Beatmapset not found")
    return BeatmapsetResp.from_db(beatmapset)
