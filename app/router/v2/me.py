from __future__ import annotations

from app.database import User, UserResp
from app.database.lazer_user import ALL_INCLUDED
from app.dependencies import get_current_user
from app.dependencies.database import get_db
from app.models.score import GameMode

from .router import router

from fastapi import Depends, Path, Security
from sqlmodel.ext.asyncio.session import AsyncSession


@router.get(
    "/me/{ruleset}",
    response_model=UserResp,
    name="获取当前用户信息 (指定 ruleset)",
    description="获取当前登录用户信息 （含指定 ruleset 统计）。",
    tags=["用户"],
)
async def get_user_info_with_ruleset(
    ruleset: GameMode = Path(description="指定 ruleset"),
    current_user: User = Security(get_current_user, scopes=["identify"]),
    session: AsyncSession = Depends(get_db),
):
    return await UserResp.from_db(
        current_user,
        session,
        ALL_INCLUDED,
        ruleset,
    )


@router.get(
    "/me/",
    response_model=UserResp,
    name="获取当前用户信息",
    description="获取当前登录用户信息。",
    tags=["用户"],
)
async def get_user_info_default(
    current_user: User = Security(get_current_user, scopes=["identify"]),
    session: AsyncSession = Depends(get_db),
):
    return await UserResp.from_db(
        current_user,
        session,
        ALL_INCLUDED,
        None,
    )
