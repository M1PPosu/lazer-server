from typing import Annotated

from app.auth import (
    authenticate_user,
    get_password_hash,
    validate_password,
)
from app.database.auth import OAuthToken
from app.database.verification import LoginSession, TrustedDevice
from app.dependencies.database import Database
from app.dependencies.user import ClientUser
from app.log import log

from .router import router

from fastapi import Depends, Form, HTTPException
from fastapi_limiter.depends import RateLimiter
from sqlmodel import col, delete

logger = log("Auth")


@router.post(
    "/password/change",
    name="更改密码",
    tags=["验证", "g0v0 API"],
    status_code=204,
    dependencies=[Depends(RateLimiter(times=3, minutes=5))],
)
async def change_password(
    current_user: ClientUser,
    session: Database,
    current_password: Annotated[str, Form(..., description="当前密码")],
    new_password: Annotated[str, Form(..., description="新密码")],
):
    """更改用户密码

    同时删除所有的已登录会话和信任设备

    速率限制: 5 分钟内最多 3 次
    """
    if not await authenticate_user(session, current_user.username, current_password):
        raise HTTPException(status_code=403, detail="Password incorrect")
    if errors := validate_password(new_password):
        raise HTTPException(status_code=400, detail="; ".join(errors))

    current_user.pw_bcrypt = get_password_hash(new_password)

    await session.execute(delete(TrustedDevice).where(col(TrustedDevice.user_id) == current_user.id))
    await session.execute(delete(LoginSession).where(col(LoginSession.user_id) == current_user.id))
    await session.execute(delete(OAuthToken).where(col(OAuthToken.user_id) == current_user.id))
    logger.info(f"User {current_user.id} changed password and sessions revoked")
    await session.commit()
