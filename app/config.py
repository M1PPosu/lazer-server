from __future__ import annotations

from enum import Enum
from typing import Annotated, Any

from pydantic import Field, HttpUrl, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class AWSS3StorageSettings(BaseSettings):
    s3_access_key_id: str
    s3_secret_access_key: str
    s3_bucket_name: str
    s3_region_name: str
    s3_public_url_base: str | None = None


class CloudflareR2Settings(BaseSettings):
    r2_account_id: str
    r2_access_key_id: str
    r2_secret_access_key: str
    r2_bucket_name: str
    r2_public_url_base: str | None = None


class LocalStorageSettings(BaseSettings):
    local_storage_path: str = "./storage"


class StorageServiceType(str, Enum):
    LOCAL = "local"
    CLOUDFLARE_R2 = "r2"
    AWS_S3 = "s3"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # 数据库设置
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_database: str = "osu_api"
    mysql_user: str = "osu_api"
    mysql_password: str = "password"
    mysql_root_password: str = "password"
    redis_url: str = "redis://127.0.0.1:6379/0"

    @property
    def database_url(self) -> str:
        return f"mysql+aiomysql://{self.mysql_user}:{self.mysql_password}@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"

    # JWT 设置
    secret_key: str = Field(default="your_jwt_secret_here", alias="jwt_secret_key")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    # OAuth 设置
    osu_client_id: int = 5
    osu_client_secret: str = "FGc9GAtyHzeQDshWP5Ah7dega8hJACAJpQtw6OXk"
    osu_web_client_id: int = 6
    osu_web_client_secret: str = "your_osu_web_client_secret_here"

    # 服务器设置
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    cors_urls: list[HttpUrl] = []
    server_url: HttpUrl = HttpUrl("http://localhost:8000")
    frontend_url: HttpUrl | None = None

    # SignalR 设置
    signalr_negotiate_timeout: int = 30
    signalr_ping_interval: int = 15

    # Fetcher 设置
    fetcher_client_id: str = ""
    fetcher_client_secret: str = ""
    fetcher_scopes: Annotated[list[str], NoDecode] = ["public"]

    @property
    def fetcher_callback_url(self) -> str:
        return f"{self.server_url}fetcher/callback"

    # 日志设置
    log_level: str = "INFO"

    # Sentry 配置
    sentry_dsn: HttpUrl | None = None

    # 游戏设置
    enable_osu_rx: bool = False
    enable_osu_ap: bool = False
    enable_all_mods_pp: bool = False
    enable_supporter_for_all_users: bool = False
    enable_all_beatmap_leaderboard: bool = False
    enable_all_beatmap_pp: bool = False
    seasonal_backgrounds: list[str] = []

    # 存储设置
    storage_service: StorageServiceType = StorageServiceType.LOCAL
    storage_settings: (
        LocalStorageSettings | CloudflareR2Settings | AWSS3StorageSettings
    ) = LocalStorageSettings()

    @field_validator("fetcher_scopes", mode="before")
    def validate_fetcher_scopes(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            return v.split(",")
        return v

    @field_validator("storage_settings", mode="after")
    def validate_storage_settings(
        cls,
        v: LocalStorageSettings | CloudflareR2Settings | AWSS3StorageSettings,
        info: ValidationInfo,
    ) -> LocalStorageSettings | CloudflareR2Settings | AWSS3StorageSettings:
        if info.data.get("storage_service") == StorageServiceType.CLOUDFLARE_R2:
            if not isinstance(v, CloudflareR2Settings):
                raise ValueError(
                    "When storage_service is 'r2', "
                    "storage_settings must be CloudflareR2Settings"
                )
        elif info.data.get("storage_service") == StorageServiceType.LOCAL:
            if not isinstance(v, LocalStorageSettings):
                raise ValueError(
                    "When storage_service is 'local', "
                    "storage_settings must be LocalStorageSettings"
                )
        elif info.data.get("storage_service") == StorageServiceType.AWS_S3:
            if not isinstance(v, AWSS3StorageSettings):
                raise ValueError(
                    "When storage_service is 's3', "
                    "storage_settings must be AWSS3StorageSettings"
                )
        return v


settings = Settings()
