from __future__ import annotations

from typing import Literal

from app.database import User as DBUser
from app.dependencies import get_db, get_current_user
from app.models.user import User as ApiUser
from app.utils import convert_db_user_to_api_user

from .api_router import router

from fastapi import Depends, HTTPException, Query
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession


async def get_user_by_lookup(
    db: AsyncSession,
    lookup: str,
    key: str = "id"
) -> DBUser | None:
    """根据查找方式获取用户"""
    if key == "id":
        try:
            user_id = int(lookup)
            result = await db.exec(
                select(DBUser).where(DBUser.id == user_id)
            )
            return result.first()
        except ValueError:
            return None
    elif key == "username":
        result = await db.exec(
            select(DBUser).where(DBUser.name == lookup)
        )
        return result.first()
    else:
        return None



@router.get("/users/{user_lookup}/{mode}", response_model=ApiUser)
@router.get("/users/{user_lookup}/{mode}/", response_model=ApiUser)
async def get_user_with_mode(
    user_lookup: str,
    mode: Literal["osu", "taiko", "fruits", "mania"],
    key: Literal["id", "username"] = Query("id"),
    current_user: DBUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取指定游戏模式的用户信息"""
    user = await get_user_by_lookup(db, user_lookup, key)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    api_user = await convert_db_user_to_api_user(user, mode)
    return api_user


@router.get("/users/{user_lookup}", response_model=ApiUser)
@router.get("/users/{user_lookup}/", response_model=ApiUser)
async def get_user_default(
    user_lookup: str,
    key: Literal["id", "username"] = Query("id"),
    current_user: DBUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取用户信息（默认使用osu模式，但包含所有模式的统计信息）"""
    user = await get_user_by_lookup(db, user_lookup, key)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    api_user = await convert_db_user_to_api_user(user, "osu")
    return api_user
