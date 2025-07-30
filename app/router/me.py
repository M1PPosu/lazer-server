from __future__ import annotations

from app.database import User, UserResp
from app.dependencies import get_current_user
from app.dependencies.database import get_db
from app.models.score import GameMode

from .api_router import router

from fastapi import Depends
from sqlmodel.ext.asyncio.session import AsyncSession


@router.get("/me/{ruleset}", response_model=UserResp)
@router.get("/me/", response_model=UserResp)
async def get_user_info_default(
    ruleset: GameMode | None = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await UserResp.from_db(
        current_user,
        session,
        [
            "friends",
            "team",
            "account_history",
            "daily_challenge_user_stats",
            "statistics",
            "statistics_rulesets",
            "achievements",
        ],
        ruleset,
    )
