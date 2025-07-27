from __future__ import annotations

from app.auth import get_token_by_access_token
from app.database import (
    User as DBUser,
)

from .database import get_db

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import joinedload, selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> DBUser:
    """获取当前认证用户"""
    token = credentials.credentials

    user = await get_current_user_by_token(token, db)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user


async def get_current_user_by_token(token: str, db: AsyncSession) -> DBUser | None:
    token_record = await get_token_by_access_token(db, token)
    if not token_record:
        return None
    user = (
        await db.exec(
            select(DBUser)
            .options(
                joinedload(DBUser.lazer_profile),  # pyright: ignore[reportArgumentType]
                joinedload(DBUser.lazer_counts),  # pyright: ignore[reportArgumentType]
                joinedload(DBUser.daily_challenge_stats),  # pyright: ignore[reportArgumentType]
                joinedload(DBUser.avatar),  # pyright: ignore[reportArgumentType]
                selectinload(DBUser.lazer_statistics),  # pyright: ignore[reportArgumentType]
                selectinload(DBUser.lazer_achievements),  # pyright: ignore[reportArgumentType]
                selectinload(DBUser.lazer_profile_sections),  # pyright: ignore[reportArgumentType]
                selectinload(DBUser.statistics),  # pyright: ignore[reportArgumentType]
                joinedload(DBUser.team_membership),  # pyright: ignore[reportArgumentType]
                selectinload(DBUser.rank_history),  # pyright: ignore[reportArgumentType]
                selectinload(DBUser.active_banners),  # pyright: ignore[reportArgumentType]
                selectinload(DBUser.lazer_badges),  # pyright: ignore[reportArgumentType]
                selectinload(DBUser.lazer_monthly_playcounts),  # pyright: ignore[reportArgumentType]
                selectinload(DBUser.lazer_previous_usernames),  # pyright: ignore[reportArgumentType]
                selectinload(DBUser.lazer_replays_watched),  # pyright: ignore[reportArgumentType]
            )
            .where(DBUser.id == token_record.user_id)
        )
    ).first()
    return user
