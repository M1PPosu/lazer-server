from __future__ import annotations

from app.database import User, UserResp
from app.database.lazer_user import ALL_INCLUDED
from app.dependencies import get_current_user
from app.dependencies.database import get_db
from app.models.score import GameMode

from .router import router

from fastapi import Depends, Security
from sqlmodel.ext.asyncio.session import AsyncSession


@router.get("/me/{ruleset}", response_model=UserResp)
@router.get("/me/", response_model=UserResp)
async def get_user_info_default(
    ruleset: GameMode | None = None,
    current_user: User = Security(get_current_user, scopes=["identify"]),
    session: AsyncSession = Depends(get_db),
):
    return await UserResp.from_db(
        current_user,
        session,
        ALL_INCLUDED,
        ruleset,
    )
