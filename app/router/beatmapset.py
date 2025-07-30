from __future__ import annotations

from app.database import (
    Beatmapset,
    BeatmapsetResp,
    User,
)
from app.dependencies.database import get_db
from app.dependencies.fetcher import get_fetcher
from app.dependencies.user import get_current_user
from app.fetcher import Fetcher

from .api_router import router

from fastapi import Depends, HTTPException
from httpx import HTTPStatusError
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession


@router.get("/beatmapsets/{sid}", tags=["beatmapset"], response_model=BeatmapsetResp)
async def get_beatmapset(
    sid: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    fetcher: Fetcher = Depends(get_fetcher),
):
    beatmapset = (
        await db.exec(
            select(Beatmapset)
            .options(selectinload(Beatmapset.beatmaps))  # pyright: ignore[reportArgumentType]
            .where(Beatmapset.id == sid)
        )
    ).first()
    if not beatmapset:
        try:
            resp = await fetcher.get_beatmapset(sid)
            await Beatmapset.from_resp(db, resp)
        except HTTPStatusError:
            raise HTTPException(status_code=404, detail="Beatmapset not found")
    else:
        resp = BeatmapsetResp.from_db(beatmapset)
    return resp
