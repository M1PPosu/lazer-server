from __future__ import annotations

from datetime import UTC, datetime, timedelta
import re
from typing import Literal

from app.auth import (
    authenticate_user,
    create_access_token,
    generate_refresh_token,
    get_password_hash,
    get_token_by_refresh_token,
    get_user_by_authorization_code,
    store_token,
    validate_username,
)
from app.config import settings
from app.const import BANCHOBOT_ID
from app.database import DailyChallengeStats, OAuthClient, User
from app.database.statistics import UserStatistics
from app.dependencies.database import Database, get_redis
from app.dependencies.geoip import get_client_ip, get_geoip_helper
from app.helpers.geoip_helper import GeoIPHelper
from app.log import logger
from app.models.oauth import (
    OAuthErrorResponse,
    RegistrationRequestErrors,
    TokenResponse,
    UserRegistrationErrors,
)
from app.models.score import GameMode
from app.service.login_log_service import LoginLogService

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy import text
from sqlmodel import select


def create_oauth_error_response(
    error: str, description: str, hint: str, status_code: int = 400
):
    """创建标准的 OAuth 错误响应"""
    error_data = OAuthErrorResponse(
        error=error, error_description=description, hint=hint, message=description
    )
    return JSONResponse(status_code=status_code, content=error_data.model_dump())


def validate_email(email: str) -> list[str]:
    """验证邮箱"""
    errors = []

    if not email:
        errors.append("Email is required")
        return errors

    # 基本的邮箱格式验证
    email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(email_pattern, email):
        errors.append("Please enter a valid email address")

    return errors


def validate_password(password: str) -> list[str]:
    """验证密码"""
    errors = []

    if not password:
        errors.append("Password is required")
        return errors

    if len(password) < 8:
        errors.append("Password must be at least 8 characters long")

    return errors


router = APIRouter(tags=["osu! OAuth 认证"])


@router.post(
    "/users",
    name="注册用户",
    description="用户注册接口",
)
async def register_user(
    db: Database,
    request: Request,
    user_username: str = Form(..., alias="user[username]", description="用户名"),
    user_email: str = Form(..., alias="user[user_email]", description="电子邮箱"),
    user_password: str = Form(..., alias="user[password]", description="密码"),
    geoip: GeoIPHelper = Depends(get_geoip_helper),
):
    username_errors = validate_username(user_username)
    email_errors = validate_email(user_email)
    password_errors = validate_password(user_password)

    result = await db.exec(select(User).where(User.username == user_username))
    existing_user = result.first()
    if existing_user:
        username_errors.append("Username is already taken")

    result = await db.exec(select(User).where(User.email == user_email))
    existing_email = result.first()
    if existing_email:
        email_errors.append("Email is already taken")

    if username_errors or email_errors or password_errors:
        errors = RegistrationRequestErrors(
            user=UserRegistrationErrors(
                username=username_errors,
                user_email=email_errors,
                password=password_errors,
            )
        )

        return JSONResponse(
            status_code=422, content={"form_error": errors.model_dump()}
        )

    try:
        # 获取客户端 IP 并查询地理位置
        client_ip = get_client_ip(request)
        country_code = "CN"  # 默认国家代码

        try:
            # 查询 IP 地理位置
            geo_info = geoip.lookup(client_ip)
            if geo_info and geo_info.get("country_iso"):
                country_code = geo_info["country_iso"]
                logger.info(
                    f"User {user_username} registering from "
                    f"{client_ip}, country: {country_code}"
                )
            else:
                logger.warning(f"Could not determine country for IP {client_ip}")
        except Exception as e:
            logger.warning(f"GeoIP lookup failed for {client_ip}: {e}")

        # 创建新用户
        # 确保 AUTO_INCREMENT 值从3开始（ID=1是BanchoBot，ID=2预留给ppy）
        result = await db.execute(  # pyright: ignore[reportDeprecated]
            text(
                "SELECT AUTO_INCREMENT FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'lazer_users'"
            )
        )
        next_id = result.one()[0]
        if next_id <= 2:
            await db.execute(text("ALTER TABLE lazer_users AUTO_INCREMENT = 3"))
            await db.commit()

        new_user = User(
            username=user_username,
            email=user_email,
            pw_bcrypt=get_password_hash(user_password),
            priv=1,  # 普通用户权限
            country_code=country_code,  # 根据 IP 地理位置设置国家
            join_date=datetime.now(UTC),
            last_visit=datetime.now(UTC),
            is_supporter=settings.enable_supporter_for_all_users,
            support_level=int(settings.enable_supporter_for_all_users),
        )
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        assert new_user.id is not None, "New user ID should not be None"
        for i in [GameMode.OSU, GameMode.TAIKO, GameMode.FRUITS, GameMode.MANIA]:
            statistics = UserStatistics(mode=i, user_id=new_user.id)
            db.add(statistics)
        if settings.enable_rx:
            for mode in (GameMode.OSURX, GameMode.TAIKORX, GameMode.FRUITSRX):
                statistics_rx = UserStatistics(mode=mode, user_id=new_user.id)
                db.add(statistics_rx)
        if settings.enable_ap:
            statistics_ap = UserStatistics(mode=GameMode.OSUAP, user_id=new_user.id)
            db.add(statistics_ap)
        daily_challenge_user_stats = DailyChallengeStats(user_id=new_user.id)
        db.add(daily_challenge_user_stats)
        await db.commit()
    except Exception:
        await db.rollback()
        # 打印详细错误信息用于调试
        logger.exception(f"Registration error for user {user_username}")

        # 返回通用错误
        errors = RegistrationRequestErrors(
            message="An error occurred while creating your account. Please try again."
        )

        return JSONResponse(
            status_code=500, content={"form_error": errors.model_dump()}
        )


@router.post(
    "/oauth/token",
    response_model=TokenResponse,
    name="获取访问令牌",
    description="OAuth 令牌端点，支持密码、刷新令牌和授权码三种授权方式。",
)
async def oauth_token(
    db: Database,
    request: Request,
    grant_type: Literal[
        "authorization_code", "refresh_token", "password", "client_credentials"
    ] = Form(..., description="授权类型：密码/刷新令牌/授权码/客户端凭证"),
    client_id: int = Form(..., description="客户端 ID"),
    client_secret: str = Form(..., description="客户端密钥"),
    code: str | None = Form(None, description="授权码（仅授权码模式需要）"),
    scope: str = Form("*", description="权限范围（空格分隔，默认为 '*'）"),
    username: str | None = Form(None, description="用户名（仅密码模式需要）"),
    password: str | None = Form(None, description="密码（仅密码模式需要）"),
    refresh_token: str | None = Form(
        None, description="刷新令牌（仅刷新令牌模式需要）"
    ),
    redis: Redis = Depends(get_redis),
):
    scopes = scope.split(" ")

    client = (
        await db.exec(
            select(OAuthClient).where(
                OAuthClient.client_id == client_id,
                OAuthClient.client_secret == client_secret,
            )
        )
    ).first()
    is_game_client = (client_id, client_secret) in [
        (settings.osu_client_id, settings.osu_client_secret),
        (settings.osu_web_client_id, settings.osu_web_client_secret),
    ]

    if client is None and not is_game_client:
        return create_oauth_error_response(
            error="invalid_client",
            description=(
                "Client authentication failed (e.g., unknown client, "
                "no client authentication included, "
                "or unsupported authentication method)."
            ),
            hint="Invalid client credentials",
            status_code=401,
        )

    if grant_type == "password":
        if not username or not password:
            return create_oauth_error_response(
                error="invalid_request",
                description=(
                    "The request is missing a required parameter, includes an "
                    "invalid parameter value, "
                    "includes a parameter more than once, or is otherwise malformed."
                ),
                hint="Username and password required",
            )
        if scopes != ["*"]:
            return create_oauth_error_response(
                error="invalid_scope",
                description=(
                    "The requested scope is invalid, unknown, "
                    "or malformed. The client may not request "
                    "more than one scope at a time."
                ),
                hint="Only '*' scope is allowed for password grant type",
            )

        # 验证用户
        user = await authenticate_user(db, username, password)
        if not user:
            # 记录失败的登录尝试
            await LoginLogService.record_failed_login(
                db=db,
                request=request,
                attempted_username=username,
                login_method="password",
                notes="Invalid credentials",
            )

            return create_oauth_error_response(
                error="invalid_grant",
                description=(
                    "The provided authorization grant (e.g., authorization code, "
                    "resource owner credentials) "
                    "or refresh token is invalid, expired, revoked, "
                    "does not match the redirection URI used in "
                    "the authorization request, or was issued to another client."
                ),
                hint="Incorrect sign in",
            )

        # 确保用户对象与当前会话关联
        await db.refresh(user)

        # 记录成功的登录
        user_id = getattr(user, "id")
        assert user_id is not None, "User ID should not be None after authentication"
        await LoginLogService.record_login(
            db=db,
            user_id=user_id,
            request=request,
            login_success=True,
            login_method="password",
            notes=f"OAuth password grant for client {client_id}",
        )

        # 生成令牌
        access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
        # 获取用户ID，避免触发延迟加载
        access_token = create_access_token(
            data={"sub": str(user_id)}, expires_delta=access_token_expires
        )
        refresh_token_str = generate_refresh_token()

        # 存储令牌
        assert user_id
        await store_token(
            db,
            user_id,
            client_id,
            scopes,
            access_token,
            refresh_token_str,
            settings.access_token_expire_minutes * 60,
        )

        return TokenResponse(
            access_token=access_token,
            token_type="Bearer",
            expires_in=settings.access_token_expire_minutes * 60,
            refresh_token=refresh_token_str,
            scope=scope,
        )

    elif grant_type == "refresh_token":
        # 刷新令牌流程
        if not refresh_token:
            return create_oauth_error_response(
                error="invalid_request",
                description=(
                    "The request is missing a required parameter, "
                    "includes an invalid parameter value, "
                    "includes a parameter more than once, or is otherwise malformed."
                ),
                hint="Refresh token required",
            )

        # 验证刷新令牌
        token_record = await get_token_by_refresh_token(db, refresh_token)
        if not token_record:
            return create_oauth_error_response(
                error="invalid_grant",
                description=(
                    "The provided authorization grant (e.g., authorization code, "
                    "resource owner credentials) or refresh token is "
                    "invalid, expired, revoked, "
                    "does not match the redirection URI used "
                    "in the authorization request, or was issued to another client."
                ),
                hint="Invalid refresh token",
            )

        # 生成新的访问令牌
        access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
        access_token = create_access_token(
            data={"sub": str(token_record.user_id)}, expires_delta=access_token_expires
        )
        new_refresh_token = generate_refresh_token()

        # 更新令牌
        await store_token(
            db,
            token_record.user_id,
            client_id,
            scopes,
            access_token,
            new_refresh_token,
            settings.access_token_expire_minutes * 60,
        )

        return TokenResponse(
            access_token=access_token,
            token_type="Bearer",
            expires_in=settings.access_token_expire_minutes * 60,
            refresh_token=new_refresh_token,
            scope=scope,
        )
    elif grant_type == "authorization_code":
        if client is None:
            return create_oauth_error_response(
                error="invalid_client",
                description=(
                    "Client authentication failed (e.g., unknown client, "
                    "no client authentication included, "
                    "or unsupported authentication method)."
                ),
                hint="Invalid client credentials",
                status_code=401,
            )

        if not code:
            return create_oauth_error_response(
                error="invalid_request",
                description=(
                    "The request is missing a required parameter, "
                    "includes an invalid parameter value, "
                    "includes a parameter more than once, or is otherwise malformed."
                ),
                hint="Authorization code required",
            )

        code_result = await get_user_by_authorization_code(db, redis, client_id, code)
        if not code_result:
            return create_oauth_error_response(
                error="invalid_grant",
                description=(
                    "The provided authorization grant (e.g., authorization code, "
                    "resource owner credentials) or refresh token is invalid, "
                    "expired, revoked, does not match the redirection URI used in "
                    "the authorization request, or was issued to another client."
                ),
                hint="Invalid authorization code",
            )
        user, scopes = code_result

        # 确保用户对象与当前会话关联
        await db.refresh(user)

        # 生成令牌
        access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
        # 重新查询只获取ID，避免触发延迟加载
        id_result = await db.exec(select(User.id).where(User.username == username))
        user_id = id_result.first()

        access_token = create_access_token(
            data={"sub": str(user_id)}, expires_delta=access_token_expires
        )
        refresh_token_str = generate_refresh_token()

        # 存储令牌
        assert user_id
        await store_token(
            db,
            user_id,
            client_id,
            scopes,
            access_token,
            refresh_token_str,
            settings.access_token_expire_minutes * 60,
        )

        return TokenResponse(
            access_token=access_token,
            token_type="Bearer",
            expires_in=settings.access_token_expire_minutes * 60,
            refresh_token=refresh_token_str,
            scope=" ".join(scopes),
        )
    elif grant_type == "client_credentials":
        if client is None:
            return create_oauth_error_response(
                error="invalid_client",
                description=(
                    "Client authentication failed (e.g., unknown client, "
                    "no client authentication included, "
                    "or unsupported authentication method)."
                ),
                hint="Invalid client credentials",
                status_code=401,
            )
        elif scopes != ["public"]:
            return create_oauth_error_response(
                error="invalid_scope",
                description="The requested scope is invalid, unknown, or malformed.",
                hint="Scope must be 'public'",
                status_code=400,
            )

        # 生成令牌
        access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
        access_token = create_access_token(
            data={"sub": "3"}, expires_delta=access_token_expires
        )
        refresh_token_str = generate_refresh_token()

        # 存储令牌
        await store_token(
            db,
            BANCHOBOT_ID,
            client_id,
            scopes,
            access_token,
            refresh_token_str,
            settings.access_token_expire_minutes * 60,
        )

        return TokenResponse(
            access_token=access_token,
            token_type="Bearer",
            expires_in=settings.access_token_expire_minutes * 60,
            refresh_token=refresh_token_str,
            scope=" ".join(scopes),
        )
