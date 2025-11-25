import asyncio
from datetime import datetime
import time

from app.dependencies.database import get_redis
from app.log import fetcher_logger

from httpx import AsyncClient, HTTPStatusError, TimeoutException


class TokenAuthError(Exception):
    """Token 授权失败异常"""

    pass


class PassiveRateLimiter:
    """
    被动速率限制器
    当收到 429 响应时，读取 Retry-After 头并暂停所有请求
    """

    def __init__(self):
        self._lock = asyncio.Lock()
        self._retry_after_time: float | None = None
        self._waiting_tasks: set[asyncio.Task] = set()

    async def wait_if_limited(self) -> None:
        """如果正在限流中，等待限流解除"""
        async with self._lock:
            if self._retry_after_time is not None:
                current_time = time.time()
                if current_time < self._retry_after_time:
                    wait_seconds = self._retry_after_time - current_time
                    logger.warning(f"Rate limited, waiting {wait_seconds:.2f} seconds")
                    await asyncio.sleep(wait_seconds)
                    self._retry_after_time = None

    async def handle_rate_limit(self, retry_after: str | int | None) -> None:
        """
        处理 429 响应，设置限流时间

        Args:
            retry_after: Retry-After 头的值，可以是秒数或 HTTP 日期
        """
        async with self._lock:
            if retry_after is None:
                # 如果没有 Retry-After 头，默认等待 60 秒
                wait_seconds = 60
            elif isinstance(retry_after, int):
                wait_seconds = retry_after
            elif retry_after.isdigit():
                wait_seconds = int(retry_after)
            else:
                # 尝试解析 HTTP 日期格式
                try:
                    retry_time = datetime.strptime(retry_after, "%a, %d %b %Y %H:%M:%S %Z")
                    wait_seconds = max(0, (retry_time - datetime.utcnow()).total_seconds())
                except ValueError:
                    # 解析失败，默认等待 60 秒
                    wait_seconds = 60

            self._retry_after_time = time.time() + wait_seconds
            logger.warning(f"Rate limit triggered, will retry after {wait_seconds} seconds")


logger = fetcher_logger("Fetcher")


class BaseFetcher:
    # 类级别的 rate limiter，所有实例共享
    _rate_limiter = PassiveRateLimiter()

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
        self._token_lock = asyncio.Lock()

    # NOTE: Reserve for user-based fetchers
    # @property
    # def authorize_url(self) -> str:
    #     return (
    #         f"https://osu.ppy.sh/oauth/authorize?client_id={self.client_id}"
    #         f"&response_type=code&scope={quote(' '.join(self.scope))}"
    #         f"&redirect_uri={self.callback_url}"
    #     )

    @property
    def header(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    async def request_api(self, url: str, method: str = "GET", **kwargs) -> dict:
        """
        发送 API 请求，支持被动速率限制
        """
        await self.ensure_valid_access_token()

        headers = kwargs.pop("headers", {}).copy()
        attempt = 0

        while attempt < 2:
            # 在发送请求前等待速率限制
            await self._rate_limiter.wait_if_limited()

            request_headers = {**headers, **self.header}
            request_kwargs = kwargs.copy()

            async with AsyncClient() as client:
                try:
                    response = await client.request(
                        method,
                        url,
                        headers=request_headers,
                        **request_kwargs,
                    )
                    response.raise_for_status()
                    return response.json()

                except HTTPStatusError as e:
                    # 处理 429 速率限制响应
                    if e.response.status_code == 429:
                        retry_after = e.response.headers.get("Retry-After")
                        logger.warning(f"Rate limited for {url}, Retry-After: {retry_after}")
                        await self._rate_limiter.handle_rate_limit(retry_after)
                        # 速率限制后重试当前请求（不增加 attempt）
                        continue

                    # 处理 401 未授权响应
                    if e.response.status_code == 401:
                        attempt += 1
                        logger.warning(f"Received 401 error for {url}, attempt {attempt}")
                        await self._handle_unauthorized()
                        continue

                    # 其他 HTTP 错误直接抛出
                    raise

        await self._clear_access_token()
        logger.warning(f"Failed to authorize after retries for {url}, cleaned up tokens")
        await self.grant_access_token()
        raise TokenAuthError(f"Failed to authorize after retries for {url}")

    def is_token_expired(self) -> bool:
        if not isinstance(self.token_expiry, int):
            return True
        return self.token_expiry <= int(time.time()) or not self.access_token

    async def grant_access_token(self, retries: int = 3, backoff: float = 1.0) -> None:
        last_error: Exception | None = None
        async with AsyncClient(timeout=30.0) as client:
            for attempt in range(1, retries + 1):
                try:
                    response = await client.post(
                        "https://osu.ppy.sh/oauth/token",
                        data={
                            "client_id": self.client_id,
                            "client_secret": self.client_secret,
                            "grant_type": "client_credentials",
                            "scope": "public",
                        },
                    )
                    response.raise_for_status()
                    token_data = response.json()
                    self.access_token = token_data["access_token"]
                    self.token_expiry = int(time.time()) + token_data["expires_in"]
                    redis = get_redis()
                    await redis.set(
                        f"fetcher:access_token:{self.client_id}",
                        self.access_token,
                        ex=token_data["expires_in"],
                    )
                    await redis.set(
                        f"fetcher:expire_at:{self.client_id}",
                        self.token_expiry,
                        ex=token_data["expires_in"],
                    )
                    logger.success(
                        f"Granted new access token for client {self.client_id}, expires in {token_data['expires_in']} seconds"
                    )
                    return

                except TimeoutException as exc:
                    last_error = exc
                    logger.warning(
                        f"Timed out while requesting access token for client {self.client_id} (attempt {attempt}/{retries})"
                    )
                except HTTPStatusError as exc:
                    last_error = exc
                    logger.warning(
                        f"HTTP error while requesting access token for client {self.client_id}"
                        f" (status: {exc.response.status_code}, attempt {attempt}/{retries})"
                    )
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
                    logger.exception(
                        f"Unexpected error while requesting access token for client {self.client_id}"
                        f" (attempt {attempt}/{retries})"
                    )

                if attempt < retries:
                    await asyncio.sleep(backoff * attempt)

        raise TokenAuthError("Failed to grant access token after retries") from last_error

    async def ensure_valid_access_token(self) -> None:
        if self.is_token_expired():
            await self.grant_access_token()

    async def _handle_unauthorized(self) -> None:
        await self.grant_access_token()

    async def _clear_access_token(self) -> None:
        logger.warning(f"Clearing access token for client {self.client_id}")

        self.access_token = ""
        self.token_expiry = 0

        redis = get_redis()
        await redis.delete(f"fetcher:access_token:{self.client_id}")
        await redis.delete(f"fetcher:expire_at:{self.client_id}")
