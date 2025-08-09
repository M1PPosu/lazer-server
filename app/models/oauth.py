# OAuth 相关模型
from __future__ import annotations

from pydantic import BaseModel


class TokenRequest(BaseModel):
    grant_type: str
    username: str | None = None
    password: str | None = None
    refresh_token: str | None = None
    client_id: str
    client_secret: str
    scope: str = "*"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    refresh_token: str
    scope: str = "*"


class UserCreate(BaseModel):
    username: str
    password: str
    email: str
    country_code: str = "CN"


class OAuthErrorResponse(BaseModel):
    error: str
    error_description: str
    hint: str
    message: str


class RegistrationErrorResponse(BaseModel):
    """注册错误响应模型"""

    form_error: dict


class UserRegistrationErrors(BaseModel):
    """用户注册错误模型"""

    username: list[str] = []
    user_email: list[str] = []
    password: list[str] = []


class RegistrationRequestErrors(BaseModel):
    """注册请求错误模型"""

    message: str | None = None
    redirect: str | None = None
    user: UserRegistrationErrors | None = None
