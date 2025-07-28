from __future__ import annotations

from datetime import timedelta
import re
from typing import List

from app.auth import (
    authenticate_user,
    create_access_token,
    generate_refresh_token,
    get_token_by_refresh_token,
    store_token,
    get_password_hash,
)
from app.config import settings
from app.dependencies import get_db
from app.models.oauth import TokenResponse, OAuthErrorResponse, RegistrationErrorResponse, UserRegistrationErrors, RegistrationRequestErrors
from app.database import User as DBUser

from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.responses import JSONResponse
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession


def create_oauth_error_response(error: str, description: str, hint: str, status_code: int = 400):
    """创建标准的 OAuth 错误响应"""
    error_data = OAuthErrorResponse(
        error=error,
        error_description=description,
        hint=hint,
        message=description
    )
    return JSONResponse(
        status_code=status_code,
        content=error_data.model_dump()
    )



def validate_username(username: str) -> List[str]:
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
    if not re.match(r'^[a-zA-Z0-9_-]+$', username):
        errors.append("Username can only contain letters, numbers, underscores, and hyphens")

    # 检查是否以数字开头
    if username[0].isdigit():
        errors.append("Username cannot start with a number")

    return errors


def validate_email(email: str) -> List[str]:
    """验证邮箱"""
    errors = []

    if not email:
        errors.append("Email is required")
        return errors

    # 基本的邮箱格式验证
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        errors.append("Please enter a valid email address")

    return errors


def validate_password(password: str) -> List[str]:
    """验证密码"""
    errors = []

    if not password:
        errors.append("Password is required")
        return errors

    if len(password) < 8:
        errors.append("Password must be at least 8 characters long")

    return errors


router = APIRouter(tags=["osu! OAuth 认证"])


@router.post("/users")
async def register_user(
    user_username: str = Form(..., alias="user[username]"),
    user_email: str = Form(..., alias="user[user_email]"),
    user_password: str = Form(..., alias="user[password]"),
    db: AsyncSession = Depends(get_db),
):
    """用户注册接口 - 匹配 osu! 客户端的注册请求"""

    username_errors = validate_username(user_username)
    email_errors = validate_email(user_email)
    password_errors = validate_password(user_password)

    result = await db.exec(
        select(DBUser).where(DBUser.name == user_username)
    )
    existing_user = result.first()
    if existing_user:
        username_errors.append("Username is already taken")

    result = await db.exec(
        select(DBUser).where(DBUser.email == user_email)
    )
    existing_email = result.first()
    if existing_email:
        email_errors.append("Email is already taken")

    if username_errors or email_errors or password_errors:
        errors = RegistrationRequestErrors(
            user=UserRegistrationErrors(
                username=username_errors,
                user_email=email_errors,
                password=password_errors
            )
        )

        return JSONResponse(
            status_code=422,
            content={"form_error": errors.model_dump()}
        )

    try:
        # 创建新用户
        from datetime import datetime
        import time

        new_user = DBUser(
            name=user_username,
            safe_name=user_username.lower(),  # 安全用户名（小写）
            email=user_email,
            pw_bcrypt=get_password_hash(user_password),
            priv=1,  # 普通用户权限
            country="CN",  # 默认国家
            creation_time=int(time.time()),
            latest_activity=int(time.time()),
            preferred_mode=0,  # 默认模式
            play_style=0,  # 默认游戏风格
        )

        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)

        # 保存用户ID，因为会话可能会关闭
        user_id = new_user.id

        if user_id <= 2:
            await db.rollback()
            try:
                from sqlalchemy import text

                # 确保 AUTO_INCREMENT 值从3开始（ID=1是BanchoBot，ID=2预留给ppy）
                await db.execute(text("ALTER TABLE users AUTO_INCREMENT = 3"))
                await db.commit()

                # 重新创建用户
                new_user = DBUser(
                    name=user_username,
                    safe_name=user_username.lower(),
                    email=user_email,
                    pw_bcrypt=get_password_hash(user_password),
                    priv=1,
                    country="CN",
                    creation_time=int(time.time()),
                    latest_activity=int(time.time()),
                    preferred_mode=0,
                    play_style=0,
                )

                db.add(new_user)
                await db.commit()
                await db.refresh(new_user)
                user_id = new_user.id

                # 最终检查ID是否有效
                if user_id <= 2:
                    await db.rollback()
                    errors = RegistrationRequestErrors(
                        message="Failed to create account with valid ID. Please contact support."
                    )
                    return JSONResponse(
                        status_code=500,
                        content={"form_error": errors.model_dump()}
                    )

            except Exception as fix_error:
                await db.rollback()
                print(f"Failed to fix AUTO_INCREMENT: {fix_error}")
                errors = RegistrationRequestErrors(
                    message="Failed to create account with valid ID. Please try again."
                )
                return JSONResponse(
                    status_code=500,
                    content={"form_error": errors.model_dump()}
                )

        # 创建默认的 lazer_profile
        from app.database.user import LazerUserProfile
        lazer_profile = LazerUserProfile(
            user_id=user_id,
            is_active=True,
            is_bot=False,
            is_deleted=False,
            is_online=True,
            is_supporter=False,
            is_restricted=False,
            session_verified=False,
            has_supported=False,
            pm_friends_only=False,
            default_group="default",
            join_date=datetime.utcnow(),
            playmode="osu",
            support_level=0,
            max_blocks=50,
            max_friends=250,
            post_count=0,
        )

        db.add(lazer_profile)
        await db.commit()

        # 返回成功响应
        return JSONResponse(
            status_code=201,
            content={
                "message": "Account created successfully",
                "user_id": user_id
            }
        )

    except Exception as e:
        await db.rollback()
        # 打印详细错误信息用于调试
        print(f"Registration error: {e}")
        import traceback
        traceback.print_exc()

        # 返回通用错误
        errors = RegistrationRequestErrors(
            message="An error occurred while creating your account. Please try again."
        )

        return JSONResponse(
            status_code=500,
            content={"form_error": errors.model_dump()}
        )


@router.post("/oauth/token", response_model=TokenResponse)
async def oauth_token(
    grant_type: str = Form(...),
    client_id: str = Form(...),
    client_secret: str = Form(...),
    scope: str = Form("*"),
    username: str | None = Form(None),
    password: str | None = Form(None),
    refresh_token: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """OAuth 令牌端点"""
    # 验证客户端凭据
    if (
        client_id != settings.OSU_CLIENT_ID
        or client_secret != settings.OSU_CLIENT_SECRET
    ):
        return create_oauth_error_response(
            error="invalid_client",
            description="Client authentication failed (e.g., unknown client, no client authentication included, or unsupported authentication method).",
            hint="Invalid client credentials",
            status_code=401
        )

    if grant_type == "password":
        # 密码授权流程
        if not username or not password:
            return create_oauth_error_response(
                error="invalid_request",
                description="The request is missing a required parameter, includes an invalid parameter value, includes a parameter more than once, or is otherwise malformed.",
                hint="Username and password required"
            )

        # 验证用户
        user = await authenticate_user(db, username, password)
        if not user:
            return create_oauth_error_response(
                error="invalid_grant",
                description="The provided authorization grant (e.g., authorization code, resource owner credentials) or refresh token is invalid, expired, revoked, does not match the redirection URI used in the authorization request, or was issued to another client.",
                hint="Incorrect sign in"
            )

        # 生成令牌
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": str(user.id)}, expires_delta=access_token_expires
        )
        refresh_token_str = generate_refresh_token()

        # 存储令牌
        await store_token(
            db,
            user.id,
            access_token,
            refresh_token_str,
            settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

        return TokenResponse(
            access_token=access_token,
            token_type="Bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            refresh_token=refresh_token_str,
            scope=scope,
        )

    elif grant_type == "refresh_token":
        # 刷新令牌流程
        if not refresh_token:
            return create_oauth_error_response(
                error="invalid_request",
                description="The request is missing a required parameter, includes an invalid parameter value, includes a parameter more than once, or is otherwise malformed.",
                hint="Refresh token required"
            )

        # 验证刷新令牌
        token_record = await get_token_by_refresh_token(db, refresh_token)
        if not token_record:
            return create_oauth_error_response(
                error="invalid_grant",
                description="The provided authorization grant (e.g., authorization code, resource owner credentials) or refresh token is invalid, expired, revoked, does not match the redirection URI used in the authorization request, or was issued to another client.",
                hint="Invalid refresh token"
            )

        # 生成新的访问令牌
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": str(token_record.user_id)}, expires_delta=access_token_expires
        )
        new_refresh_token = generate_refresh_token()

        # 更新令牌
        await store_token(
            db,
            token_record.user_id,
            access_token,
            new_refresh_token,
            settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

        return TokenResponse(
            access_token=access_token,
            token_type="Bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            refresh_token=new_refresh_token,
            scope=scope,
        )

    else:
        return create_oauth_error_response(
            error="unsupported_grant_type",
            description="The authorization grant type is not supported by the authorization server.",
            hint="Unsupported grant type"
        )
