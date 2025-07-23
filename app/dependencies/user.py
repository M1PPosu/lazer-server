from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth import get_token_by_access_token

from .database import get_db
from app.database import (
    User as DBUser,
)

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> DBUser:
    """获取当前认证用户"""
    token = credentials.credentials

    # 验证令牌
    token_record = get_token_by_access_token(db, token)
    if not token_record:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    # 获取用户
    user = db.query(DBUser).filter(DBUser.id == token_record.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user
