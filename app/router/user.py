from __future__ import annotations

from typing import Literal

from app.database import User as DBUser
from app.dependencies.database import get_db
from app.models.score import INT_TO_MODE
from app.models.user import User as ApiUser
from app.utils import convert_db_user_to_api_user

from .api_router import router

from fastapi import Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel.sql.expression import col


# ---------- Shared Utility ----------
async def get_user_by_lookup(
    db: AsyncSession, lookup: str, key: str = "id"
) -> DBUser | None:
    """根据查找方式获取用户"""
    if key == "id":
        try:
            user_id = int(lookup)
            result = await db.exec(select(DBUser).where(DBUser.id == user_id))
            return result.first()
        except ValueError:
            return None
    elif key == "username":
        result = await db.exec(select(DBUser).where(DBUser.name == lookup))
        return result.first()
    else:
        return None


# ---------- Batch Users ----------
class BatchUserResponse(BaseModel):
    users: list[ApiUser]


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
            await session.exec(
                DBUser.all_select_clause().limit(50).where(col(DBUser.id).in_(user_ids))
            )
        ).all()
    else:
        searched_users = (
            await session.exec(DBUser.all_select_clause().limit(50))
        ).all()
    return BatchUserResponse(
        users=[
            await convert_db_user_to_api_user(
                searched_user, ruleset=INT_TO_MODE[searched_user.preferred_mode].value
            )
            for searched_user in searched_users
        ]
    )


# # ---------- Individual User ----------
# @router.get("/users/{user_lookup}/{mode}", response_model=ApiUser)
# @router.get("/users/{user_lookup}/{mode}/", response_model=ApiUser)
# async def get_user_with_mode(
#     user_lookup: str,
#     mode: Literal["osu", "taiko", "fruits", "mania"],
#     key: Literal["id", "username"] = Query("id"),
#     current_user: DBUser = Depends(get_current_user),
#     db: AsyncSession = Depends(get_db),
# ):
#     """获取指定游戏模式的用户信息"""
#     user = await get_user_by_lookup(db, user_lookup, key)
#     if not user:
#         raise HTTPException(status_code=404, detail="User not found")

#     return await convert_db_user_to_api_user(user, mode)


# @router.get("/users/{user_lookup}", response_model=ApiUser)
# @router.get("/users/{user_lookup}/", response_model=ApiUser)
# async def get_user_default(
#     user_lookup: str,
#     key: Literal["id", "username"] = Query("id"),
#     current_user: DBUser = Depends(get_current_user),
#     db: AsyncSession = Depends(get_db),
# ):
#     """获取用户信息（默认使用osu模式，但包含所有模式的统计信息）"""
#     user = await get_user_by_lookup(db, user_lookup, key)
#     if not user:
#         raise HTTPException(status_code=404, detail="User not found")

#     return await convert_db_user_to_api_user(user, "osu")


@router.get("/users/{user}/{ruleset}", response_model=ApiUser)
@router.get("/users/{user}/", response_model=ApiUser)
@router.get("/users/{user}", response_model=ApiUser)
async def get_user_info(
    user: str,
    ruleset: Literal["osu", "taiko", "fruits", "mania"] = "osu",
    session: AsyncSession = Depends(get_db),
):
    searched_user = (
        await session.exec(
            DBUser.all_select_clause().where(
                DBUser.id == int(user)
                if user.isdigit()
                else DBUser.name == user.removeprefix("@")
            )
        )
    ).first()
    if not searched_user:
        raise HTTPException(404, detail="User not found")
    return await convert_db_user_to_api_user(searched_user, ruleset=ruleset)
