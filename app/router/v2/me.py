from __future__ import annotations

from app.database import User
from app.database.lazer_user import ALL_INCLUDED
from app.dependencies import get_current_user
from app.dependencies.database import Database
from app.models.api_me import APIMe
from app.models.score import GameMode

from .router import router

from fastapi import Path, Security


@router.get(
    "/me/{ruleset}",
    response_model=APIMe,
    name="获取当前用户信息 (指定 ruleset)",
    description="获取当前登录用户信息 （含指定 ruleset 统计）。",
    tags=["用户"],
)
async def get_user_info_with_ruleset(
    session: Database,
    ruleset: GameMode = Path(description="指定 ruleset"),
    current_user: User = Security(get_current_user, scopes=["identify"]),
):
    user_resp = await APIMe.from_db(
        current_user,
        session,
        ALL_INCLUDED,
        ruleset,
    )
    return user_resp


@router.get(
    "/me/",
    response_model=APIMe,
    name="获取当前用户信息",
    description="获取当前登录用户信息。",
    tags=["用户"],
)
async def get_user_info_default(
    session: Database,
    current_user: User = Security(get_current_user, scopes=["identify"]),
):
    user_resp = await APIMe.from_db(
        current_user,
        session,
        ALL_INCLUDED,
        None,
    )
    return user_resp
