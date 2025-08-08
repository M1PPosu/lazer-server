from __future__ import annotations

from typing import Literal

from app.database import Beatmap, Beatmapset, BeatmapsetResp, FavouriteBeatmapset, User
from app.dependencies.database import get_db
from app.dependencies.fetcher import get_fetcher
from app.dependencies.user import get_current_user
from app.fetcher import Fetcher

from .api_router import router

from fastapi import Depends, Form, HTTPException, Query
from fastapi.responses import RedirectResponse
from httpx import HTTPError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession


@router.get("/beatmapsets/lookup", tags=["beatmapset"], response_model=BeatmapsetResp)
async def lookup_beatmapset(
    beatmap_id: int = Query(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    fetcher: Fetcher = Depends(get_fetcher),
):
    beatmap = await Beatmap.get_or_fetch(db, fetcher, bid=beatmap_id)
    resp = await BeatmapsetResp.from_db(
        beatmap.beatmapset, session=db, user=current_user
    )
    return resp


@router.get("/beatmapsets/{sid}", tags=["beatmapset"], response_model=BeatmapsetResp)
async def get_beatmapset(
    sid: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    fetcher: Fetcher = Depends(get_fetcher),
):
    try:
        beatmapset = await Beatmapset.get_or_fetch(db, fetcher, sid)
        return await BeatmapsetResp.from_db(
            beatmapset, session=db, include=["recent_favourites"], user=current_user
        )
    except HTTPError:
        raise HTTPException(status_code=404, detail="Beatmapset not found")


@router.get("/beatmapsets/{beatmapset}/download", tags=["beatmapset"])
async def download_beatmapset(
    beatmapset: int,
    no_video: bool = Query(True, alias="noVideo"),
    current_user: User = Depends(get_current_user),
):
    if current_user.country_code == "CN":
        return RedirectResponse(
            f"https://txy1.sayobot.cn/beatmaps/download/"
            f"{'novideo' if no_video else 'full'}/{beatmapset}?server=auto"
        )
    else:
        return RedirectResponse(
            f"https://api.nerinyan.moe/d/{beatmapset}?noVideo={no_video}"
        )


@router.post("/beatmapsets/{beatmapset}/favourites", tags=["beatmapset"])
async def favourite_beatmapset(
    beatmapset: int,
    action: Literal["favourite", "unfavourite"] = Form(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    existing_favourite = (
        await db.exec(
            select(FavouriteBeatmapset).where(
                FavouriteBeatmapset.user_id == current_user.id,
                FavouriteBeatmapset.beatmapset_id == beatmapset,
            )
        )
    ).first()

    if action == "favourite" and existing_favourite:
        raise HTTPException(status_code=400, detail="Already favourited")
    elif action == "unfavourite" and not existing_favourite:
        raise HTTPException(status_code=400, detail="Not favourited")

    if action == "favourite":
        favourite = FavouriteBeatmapset(
            user_id=current_user.id, beatmapset_id=beatmapset
        )
        db.add(favourite)
    else:
        await db.delete(existing_favourite)
    await db.commit()
