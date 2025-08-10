from __future__ import annotations

import time

from app.dependencies.database import get_redis

from httpx import AsyncClient


class BaseFetcher:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        scope: list[str] = ["public"],
        callback_url: str = "",
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token: str = ""
        self.refresh_token: str = ""
        self.token_expiry: int = 0
        self.callback_url: str = callback_url
        self.scope = scope

    @property
    def authorize_url(self) -> str:
        return (
            f"https://osu.ppy.sh/oauth/authorize?client_id={self.client_id}"
            f"&response_type=code&scope={' '.join(self.scope)}"
            f"&redirect_uri={self.callback_url}"
        )

    @property
    def header(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    async def request_api(self, url: str, method: str = "GET", **kwargs) -> dict:
        if self.is_token_expired():
            await self.refresh_access_token()
        header = kwargs.pop("headers", {})
        header = self.header

        async with AsyncClient() as client:
            response = await client.request(
                method,
                url,
                headers=header,
                **kwargs,
            )
            response.raise_for_status()
            return response.json()

    def is_token_expired(self) -> bool:
        return self.token_expiry <= int(time.time())

    async def grant_access_token(self, code: str) -> None:
        async with AsyncClient() as client:
            response = await client.post(
                "https://osu.ppy.sh/oauth/token",
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "authorization_code",
                    "redirect_uri": self.callback_url,
                    "code": code,
                },
            )
            response.raise_for_status()
            token_data = response.json()
            self.access_token = token_data["access_token"]
            self.refresh_token = token_data.get("refresh_token", "")
            self.token_expiry = int(time.time()) + token_data["expires_in"]
            redis = get_redis()
            await redis.set(
                f"fetcher:access_token:{self.client_id}",
                self.access_token,
                ex=token_data["expires_in"],
            )
            await redis.set(
                f"fetcher:refresh_token:{self.client_id}",
                self.refresh_token,
            )

    async def refresh_access_token(self) -> None:
        async with AsyncClient() as client:
            response = await client.post(
                "https://osu.ppy.sh/oauth/token",
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "refresh_token",
                    "refresh_token": self.refresh_token,
                },
            )
            response.raise_for_status()
            token_data = response.json()
            self.access_token = token_data["access_token"]
            self.refresh_token = token_data.get("refresh_token", "")
            self.token_expiry = int(time.time()) + token_data["expires_in"]
            redis = get_redis()
            await redis.set(
                f"fetcher:access_token:{self.client_id}",
                self.access_token,
                ex=token_data["expires_in"],
            )
            await redis.set(
                f"fetcher:refresh_token:{self.client_id}",
                self.refresh_token,
            )
