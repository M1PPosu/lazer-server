from __future__ import annotations

from typing import Literal

from app.database import Beatmap, Beatmapset, BeatmapsetResp, FavouriteBeatmapset, User
from app.dependencies.database import get_db
from app.dependencies.fetcher import get_fetcher
from app.dependencies.user import get_current_user
from app.fetcher import Fetcher

from .router import router

from fastapi import Depends, Form, HTTPException, Path, Query, Security
from fastapi.responses import RedirectResponse
from httpx import HTTPError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession


@router.get(
    "/beatmapsets/lookup",
    tags=["谱面集"],
    name="查询谱面集 (通过谱面 ID)",
    response_model=BeatmapsetResp,
    description=("通过谱面 ID 查询所属谱面集。"),
)
async def lookup_beatmapset(
    beatmap_id: int = Query(description="谱面 ID"),
    current_user: User = Security(get_current_user, scopes=["public"]),
    db: AsyncSession = Depends(get_db),
    fetcher: Fetcher = Depends(get_fetcher),
):
    beatmap = await Beatmap.get_or_fetch(db, fetcher, bid=beatmap_id)
    resp = await BeatmapsetResp.from_db(
        beatmap.beatmapset, session=db, user=current_user
    )
    return resp


@router.get(
    "/beatmapsets/{beatmapset_id}",
    tags=["谱面集"],
    name="获取谱面集详情",
    response_model=BeatmapsetResp,
    description="获取单个谱面集详情。",
)
async def get_beatmapset(
    beatmapset_id: int = Path(..., description="谱面集 ID"),
    current_user: User = Security(get_current_user, scopes=["public"]),
    db: AsyncSession = Depends(get_db),
    fetcher: Fetcher = Depends(get_fetcher),
):
    try:
        beatmapset = await Beatmapset.get_or_fetch(db, fetcher, beatmapset_id)
        return await BeatmapsetResp.from_db(
            beatmapset, session=db, include=["recent_favourites"], user=current_user
        )
    except HTTPError:
        raise HTTPException(status_code=404, detail="Beatmapset not found")


@router.get(
    "/beatmapsets/{beatmapset_id}/download",
    tags=["谱面集"],
    name="下载谱面集",
    description="**客户端专属**\n下载谱面集文件。若用户国家为 CN 则跳转国内镜像。",
)
async def download_beatmapset(
    beatmapset_id: int = Path(..., description="谱面集 ID"),
    no_video: bool = Query(True, alias="noVideo", description="是否下载无视频版本"),
    current_user: User = Security(get_current_user, scopes=["*"]),
):
    if current_user.country_code == "CN":
        return RedirectResponse(
            f"https://txy1.sayobot.cn/beatmaps/download/"
            f"{'novideo' if no_video else 'full'}/{beatmapset_id}?server=auto"
        )
    else:
        return RedirectResponse(
            f"https://api.nerinyan.moe/d/{beatmapset_id}?noVideo={no_video}"
        )


@router.post(
    "/beatmapsets/{beatmapset_id}/favourites",
    tags=["谱面集"],
    name="收藏或取消收藏谱面集",
    description="**客户端专属**\n收藏或取消收藏指定谱面集。",
)
async def favourite_beatmapset(
    beatmapset_id: int = Path(..., description="谱面集 ID"),
    action: Literal["favourite", "unfavourite"] = Form(
        description="操作类型：favourite 收藏 / unfavourite 取消收藏"
    ),
    current_user: User = Security(get_current_user, scopes=["*"]),
    db: AsyncSession = Depends(get_db),
):
    assert current_user.id is not None
    existing_favourite = (
        await db.exec(
            select(FavouriteBeatmapset).where(
                FavouriteBeatmapset.user_id == current_user.id,
                FavouriteBeatmapset.beatmapset_id == beatmapset_id,
            )
        )
    ).first()

    if (action == "favourite" and existing_favourite) or (
        action == "unfavourite" and not existing_favourite
    ):
        return

    if action == "favourite":
        favourite = FavouriteBeatmapset(
            user_id=current_user.id, beatmapset_id=beatmapset_id
        )
        db.add(favourite)
    else:
        await db.delete(existing_favourite)
    await db.commit()
