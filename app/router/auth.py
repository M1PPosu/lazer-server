from __future__ import annotations

from datetime import timedelta

from app.auth import (
    authenticate_user,
    create_access_token,
    generate_refresh_token,
    get_token_by_refresh_token,
    store_token,
)
from app.config import settings
from app.dependencies import get_db
from app.models.oauth import TokenResponse, OAuthErrorResponse

from fastapi import APIRouter, Depends, Form
from fastapi.responses import JSONResponse
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

router = APIRouter(tags=["osu! OAuth 认证"])


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
