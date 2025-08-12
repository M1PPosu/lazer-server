from __future__ import annotations

from app.database.lazer_user import User
from app.dependencies.database import get_db

from .router import router

from fastapi import Body, Depends, HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession


@router.post("/rename", tags=["rename"])
async def user_rename(
    user_id: int = Body(...),
    new_name: str = Body(...),
    session: AsyncSession = Depends(get_db),
    # currentUser: User = Depends(get_current_user)
):
    current_user = (await session.exec(select(User).where(User.id == user_id))).first()
    if current_user is None:
        raise HTTPException(404, "User not found")
    samename_user = (
        await session.exec(select(User).where(User.username == new_name))
    ).first()
    if samename_user:
        raise HTTPException(409, "Username Exisits")
    current_user.previous_usernames.append(current_user.username)
    current_user.username = new_name
    await session.commit()
    return None
