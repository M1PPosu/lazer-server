from __future__ import annotations

from typing import Literal

from app.database import (
    User as DBUser,
)
from app.dependencies import get_current_user
from app.dependencies.database import get_db
from app.models.score import INT_TO_MODE
from app.models.user import (
    User as ApiUser,
)
from app.utils import convert_db_user_to_api_user

from .api_router import router

from fastapi import Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel.sql.expression import col


@router.get("/users/{user}/{ruleset}", response_model=ApiUser)
@router.get("/users/{user}", response_model=ApiUser)
async def get_user_info_default(
    user: str,
    ruleset: Literal["osu", "taiko", "fruits", "mania"] = "osu",
    current_user: DBUser = Depends(get_current_user),
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


class BatchUserResponse(BaseModel):
    users: list[ApiUser]


@router.get("/users", response_model=BatchUserResponse)
@router.get("/users/lookup", response_model=BatchUserResponse)
async def get_users(
    user_ids: list[int] = Query(default_factory=list, alias="ids[]"),
    include_variant_statistics: bool = Query(default=False),  # TODO
    current_user: DBUser = Depends(get_current_user),
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
                searched_user, ruleset=INT_TO_MODE[current_user.preferred_mode].value
            )
            for searched_user in searched_users
        ]
    )
