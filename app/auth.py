from __future__ import annotations

from datetime import timedelta
import hashlib
import re
import secrets
import string

from app.config import settings
from app.database import (
    OAuthToken,
    User,
)
from app.log import logger
from app.utils import utcnow

import bcrypt
from jose import JWTError, jwt
from passlib.context import CryptContext
from redis.asyncio import Redis
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

# 密码哈希上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# bcrypt 缓存（模拟应用状态缓存）
bcrypt_cache = {}


def validate_username(username: str) -> list[str]:
    """验证用户名"""
    errors = []

    if not username:
        errors.append("Username is required")
        return errors

    if len(username) < 3:
        errors.append("Username must be at least 3 characters long")

    if len(username) > 15:
        errors.append("Username must be at most 15 characters long")

    # 检查用户名格式（只允许字母、数字、下划线、连字符）
    if not re.match(r"^[a-zA-Z0-9_-]+$", username):
        errors.append("Username can only contain letters, numbers, underscores, and hyphens")

    # 检查是否以数字开头
    if username[0].isdigit():
        errors.append("Username cannot start with a number")

    if username.lower() in settings.banned_name:
        errors.append("This username is not allowed")

    return errors


def verify_password_legacy(plain_password: str, bcrypt_hash: str) -> bool:
    """
    验证密码 - 使用 osu! 的验证方式
    1. 明文密码 -> MD5哈希
    2. MD5哈希 -> bcrypt验证
    """
    # 1. 明文密码转 MD5
    pw_md5 = hashlib.md5(plain_password.encode()).hexdigest().encode()

    # 2. 检查缓存
    if bcrypt_hash in bcrypt_cache:
        return bcrypt_cache[bcrypt_hash] == pw_md5

    # 3. 如果缓存中没有，进行 bcrypt 验证
    try:
        # 验证 MD5 哈希与 bcrypt 哈希
        is_valid = bcrypt.checkpw(pw_md5, bcrypt_hash.encode())

        # 如果验证成功，将结果缓存
        if is_valid:
            bcrypt_cache[bcrypt_hash] = pw_md5

        return is_valid
    except Exception:
        logger.exception("Password verification error")
        return False


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码（向后兼容）"""
    # 首先尝试新的验证方式
    if verify_password_legacy(plain_password, hashed_password):
        return True

    # 如果失败，尝试标准 bcrypt 验证
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """生成密码哈希 - 使用 osu! 的方式"""
    # 1. 明文密码 -> MD5
    pw_md5 = hashlib.md5(password.encode()).hexdigest().encode()
    # 2. MD5 -> bcrypt
    pw_bcrypt = bcrypt.hashpw(pw_md5, bcrypt.gensalt())
    return pw_bcrypt.decode()


async def authenticate_user_legacy(db: AsyncSession, name: str, password: str) -> User | None:
    """
    验证用户身份 - 使用类似 from_login 的逻辑
    """
    # 1. 明文密码转 MD5
    pw_md5 = hashlib.md5(password.encode()).hexdigest()

    # 2. 根据用户名查找用户
    statement = select(User).where(User.username == name).options()
    user = (await db.exec(statement)).first()
    if not user:
        return None

    await db.refresh(user)

    # 3. 验证密码
    if user.pw_bcrypt is None or user.pw_bcrypt == "":
        return None

    # 4. 检查缓存
    if user.pw_bcrypt in bcrypt_cache:
        if bcrypt_cache[user.pw_bcrypt] == pw_md5.encode():
            return user
        else:
            return None

    # 5. 验证 bcrypt
    try:
        is_valid = bcrypt.checkpw(pw_md5.encode(), user.pw_bcrypt.encode())
        if is_valid:
            # 缓存验证结果
            bcrypt_cache[user.pw_bcrypt] = pw_md5.encode()
            return user
    except Exception:
        logger.exception(f"Authentication error for user {name}")

    return None


async def authenticate_user(db: AsyncSession, username: str, password: str) -> User | None:
    """验证用户身份"""
    return await authenticate_user_legacy(db, username, password)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """创建访问令牌"""
    to_encode = data.copy()
    if expires_delta:
        expire = utcnow() + expires_delta
    else:
        expire = utcnow() + timedelta(minutes=settings.access_token_expire_minutes)

    # 添加标准JWT声明
    to_encode.update({"exp": expire, "jti": secrets.token_hex(16)})
    if settings.jwt_audience:
        to_encode["aud"] = settings.jwt_audience
    to_encode["iss"] = str(settings.server_url)

    # 编码JWT
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt


def generate_refresh_token() -> str:
    """生成刷新令牌"""
    length = 64
    characters = string.ascii_letters + string.digits
    return "".join(secrets.choice(characters) for _ in range(length))


async def invalidate_user_tokens(db: AsyncSession, user_id: int) -> int:
    """使指定用户的所有令牌失效

    返回删除的令牌数量
    """
    # 使用 select 先获取所有令牌
    stmt = select(OAuthToken).where(OAuthToken.user_id == user_id)
    result = await db.exec(stmt)
    tokens = result.all()

    # 逐个删除令牌
    count = 0
    for token in tokens:
        await db.delete(token)
        count += 1

    # 提交更改
    await db.commit()
    return count


def verify_token(token: str) -> dict | None:
    """验证访问令牌"""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return payload
    except JWTError:
        return None


async def store_token(
    db: AsyncSession,
    user_id: int,
    client_id: int,
    scopes: list[str],
    access_token: str,
    refresh_token: str,
    expires_in: int,
) -> OAuthToken:
    """存储令牌到数据库"""
    expires_at = utcnow() + timedelta(seconds=expires_in)

    # 删除用户的旧令牌
    statement = select(OAuthToken).where(OAuthToken.user_id == user_id, OAuthToken.client_id == client_id)
    old_tokens = (await db.exec(statement)).all()
    for token in old_tokens:
        await db.delete(token)

    # 检查是否有重复的 access_token
    duplicate_token = (await db.exec(select(OAuthToken).where(OAuthToken.access_token == access_token))).first()
    if duplicate_token:
        await db.delete(duplicate_token)

    # 创建新令牌记录
    token_record = OAuthToken(
        user_id=user_id,
        client_id=client_id,
        access_token=access_token,
        scope=",".join(scopes),
        refresh_token=refresh_token,
        expires_at=expires_at,
    )
    db.add(token_record)
    await db.commit()
    await db.refresh(token_record)
    return token_record


async def get_token_by_access_token(db: AsyncSession, access_token: str) -> OAuthToken | None:
    """根据访问令牌获取令牌记录"""
    statement = select(OAuthToken).where(
        OAuthToken.access_token == access_token,
        OAuthToken.expires_at > utcnow(),
    )
    return (await db.exec(statement)).first()


async def get_token_by_refresh_token(db: AsyncSession, refresh_token: str) -> OAuthToken | None:
    """根据刷新令牌获取令牌记录"""
    statement = select(OAuthToken).where(
        OAuthToken.refresh_token == refresh_token,
        OAuthToken.expires_at > utcnow(),
    )
    return (await db.exec(statement)).first()


async def get_user_by_authorization_code(
    db: AsyncSession, redis: Redis, client_id: int, code: str
) -> tuple[User, list[str]] | None:
    user_id = await redis.hget(f"oauth:code:{client_id}:{code}", "user_id")  # pyright: ignore[reportGeneralTypeIssues]
    scopes = await redis.hget(f"oauth:code:{client_id}:{code}", "scopes")  # pyright: ignore[reportGeneralTypeIssues]
    if not user_id or not scopes:
        return None

    await redis.hdel(f"oauth:code:{client_id}:{code}", "user_id", "scopes")  # pyright: ignore[reportGeneralTypeIssues]

    statement = select(User).where(User.id == int(user_id))
    user = (await db.exec(statement)).first()
    if user:
        await db.refresh(user)
        return (user, scopes.split(","))
    return None
