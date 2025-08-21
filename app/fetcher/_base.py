from __future__ import annotations

import time

from app.dependencies.database import get_redis
from app.log import logger

from httpx import AsyncClient


class TokenAuthError(Exception):
    """Token 授权失败异常"""

    pass


class BaseFetcher:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        scope: list[str] = ["public"],
        callback_url: str = "",
        max_retries: int = 3,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token: str = ""
        self.refresh_token: str = ""
        self.token_expiry: int = 0
        self.callback_url: str = callback_url
        self.scope = scope
        self.max_retries = max_retries
        self._auth_retry_count = 0  # 授权重试计数器

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
        """
        发送 API 请求，具有智能重试和自动重新授权机制
        """
        return await self._request_with_retry(url, method, **kwargs)

    async def _request_with_retry(
        self, url: str, method: str = "GET", max_retries: int | None = None, **kwargs
    ) -> dict:
        """
        带重试机制的请求方法
        """
        if max_retries is None:
            max_retries = self.max_retries

        last_error = None

        for attempt in range(max_retries + 1):
            try:
                # 检查 token 是否过期
                if self.is_token_expired():
                    await self.refresh_access_token()

                header = kwargs.pop("headers", {})
                header.update(self.header)

                async with AsyncClient() as client:
                    response = await client.request(
                        method,
                        url,
                        headers=header,
                        **kwargs,
                    )

                    # 处理 401 错误
                    if response.status_code == 401:
                        self._auth_retry_count += 1
                        logger.warning(
                            f"Received 401 error (attempt {attempt + 1}/{max_retries + 1}) "
                            f"for {url}, auth retry count: {self._auth_retry_count}"
                        )

                        # 如果达到最大重试次数，触发重新授权
                        if self._auth_retry_count >= self.max_retries:
                            await self._trigger_reauthorization()
                            raise TokenAuthError(
                                f"Authentication failed after {self._auth_retry_count} attempts. "
                                f"Please re-authorize using: {self.authorize_url}"
                            )

                        # 如果还有重试机会，刷新 token 后继续
                        if attempt < max_retries:
                            await self.refresh_access_token()
                            continue
                        else:
                            # 最后一次重试也失败了
                            await self._trigger_reauthorization()
                            raise TokenAuthError(
                                f"Max retries ({max_retries}) exceeded for authentication. "
                                f"Please re-authorize using: {self.authorize_url}"
                            )

                    # 请求成功，重置重试计数器
                    self._auth_retry_count = 0
                    response.raise_for_status()
                    return response.json()

            except TokenAuthError:
                # 重新抛出授权错误
                raise
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    logger.warning(
                        f"Request failed (attempt {attempt + 1}/{max_retries + 1}): {e}, retrying..."
                    )
                    continue
                else:
                    logger.error(
                        f"Request failed after {max_retries + 1} attempts: {e}"
                    )
                    break

        # 如果所有重试都失败了
        if last_error:
            raise last_error
        else:
            raise Exception(f"Request to {url} failed after {max_retries + 1} attempts")

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
        try:
            logger.info(f"Refreshing access token for client {self.client_id}")
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
                logger.info(
                    f"Successfully refreshed access token for client {self.client_id}"
                )
        except Exception as e:
            logger.error(
                f"Failed to refresh access token for client {self.client_id}: {e}"
            )
            # 清除无效的 token，要求重新授权
            self.access_token = ""
            self.refresh_token = ""
            self.token_expiry = 0
            redis = get_redis()
            await redis.delete(f"fetcher:access_token:{self.client_id}")
            await redis.delete(f"fetcher:refresh_token:{self.client_id}")
            logger.warning(
                f"Cleared invalid tokens. Please re-authorize: {self.authorize_url}"
            )
            raise

    async def _trigger_reauthorization(self) -> None:
        """
        触发重新授权流程
        清除所有 token 并重置重试计数器
        """
        logger.error(
            f"Authentication failed after {self._auth_retry_count} attempts. "
            f"Triggering reauthorization for client {self.client_id}"
        )

        # 清除内存中的 token
        self.access_token = ""
        self.refresh_token = ""
        self.token_expiry = 0
        self._auth_retry_count = 0  # 重置重试计数器

        # 清除 Redis 中的 token
        redis = get_redis()
        await redis.delete(f"fetcher:access_token:{self.client_id}")
        await redis.delete(f"fetcher:refresh_token:{self.client_id}")

        logger.warning(
            f"All tokens cleared for client {self.client_id}. "
            f"Please re-authorize using: {self.authorize_url}"
        )

    def reset_auth_retry_count(self) -> None:
        """
        重置授权重试计数器
        可以在手动重新授权后调用
        """
        self._auth_retry_count = 0
        logger.info(f"Auth retry count reset for client {self.client_id}")

    def get_auth_status(self) -> dict:
        """
        获取当前授权状态信息
        """
        return {
            "client_id": self.client_id,
            "has_access_token": bool(self.access_token),
            "has_refresh_token": bool(self.refresh_token),
            "token_expired": self.is_token_expired(),
            "auth_retry_count": self._auth_retry_count,
            "max_retries": self.max_retries,
            "authorize_url": self.authorize_url,
            "needs_reauth": self._auth_retry_count >= self.max_retries,
        }
