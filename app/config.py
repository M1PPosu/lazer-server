from __future__ import annotations

from typing import Annotated, Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # 数据库设置
    database_url: str = "mysql+aiomysql://root:password@127.0.0.1:3306/osu_api"
    redis_url: str = "redis://127.0.0.1:6379/0"

    # JWT 设置
    secret_key: str = Field(default="your-secret-key-here", alias="jwt_secret_key")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    # OAuth 设置
    osu_client_id: str = "5"
    osu_client_secret: str = "FGc9GAtyHzeQDshWP5Ah7dega8hJACAJpQtw6OXk"

    # 服务器设置
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # SignalR 设置
    signalr_negotiate_timeout: int = 30
    signalr_ping_interval: int = 15

    # Fetcher 设置
    fetcher_client_id: str = ""
    fetcher_client_secret: str = ""
    fetcher_scopes: Annotated[list[str], NoDecode] = ["public"]
    fetcher_callback_url: str = "http://localhost:8000/fetcher/callback"

    # 日志设置
    log_level: str = "INFO"

    @field_validator("fetcher_scopes", mode="before")
    def validate_fetcher_scopes(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            return v.split(",")
        return v


settings = Settings()
