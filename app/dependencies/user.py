from __future__ import annotations

from typing import Annotated

from app.auth import get_token_by_access_token
from app.config import settings
from app.database import User

from .database import get_db

from fastapi import Depends, HTTPException
from fastapi.security import (
    HTTPBearer,
    OAuth2AuthorizationCodeBearer,
    OAuth2PasswordBearer,
    SecurityScopes,
)
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

security = HTTPBearer()


oauth2_password = OAuth2PasswordBearer(
    tokenUrl="oauth/token",
    scopes={"*": "Allows access to all scopes."},
)

oauth2_code = OAuth2AuthorizationCodeBearer(
    authorizationUrl="oauth/authorize",
    tokenUrl="oauth/token",
    scopes={
        "chat.read": "Allows read chat messages on a user's behalf.",
        "chat.write": "Allows sending chat messages on a user's behalf.",
        "chat.write_manage": (
            "Allows joining and leaving chat channels on a user's behalf."
        ),
        "delegate": (
            "Allows acting as the owner of a client; "
            "only available for Client Credentials Grant."
        ),
        "forum.write": "Allows creating and editing forum posts on a user's behalf.",
        "friends.read": "Allows reading of the user's friend list.",
        "identify": "Allows reading of the public profile of the user (/me).",
        "public": "Allows reading of publicly available data on behalf of the user.",
    },
)


async def get_current_user(
    security_scopes: SecurityScopes,
    db: Annotated[AsyncSession, Depends(get_db)],
    token_pw: Annotated[str | None, Depends(oauth2_password)] = None,
    token_code: Annotated[str | None, Depends(oauth2_code)] = None,
) -> User:
    """获取当前认证用户"""
    token = token_pw or token_code
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    token_record = await get_token_by_access_token(db, token)
    if not token_record:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    is_client = token_record.client_id in (
        settings.osu_client_id,
        settings.osu_web_client_id,
    )

    if security_scopes.scopes == ["*"]:
        # client/web only
        if not token_pw or not is_client:
            raise HTTPException(status_code=401, detail="Not authenticated")
    elif not is_client:
        for scope in security_scopes.scopes:
            if scope not in token_record.scope.split(","):
                raise HTTPException(
                    status_code=403, detail=f"Insufficient scope: {scope}"
                )

    user = (await db.exec(select(User).where(User.id == token_record.user_id))).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user
