import asyncio

from app.log import fetcher_logger

from ._base import BaseFetcher

from httpx import AsyncClient, HTTPError, Limits
import redis.asyncio as redis

urls = [
    "https://osu.ppy.sh/osu/{beatmap_id}",
    "https://osu.direct/api/osu/{beatmap_id}",
    "https://catboy.best/osu/{beatmap_id}",
]

logger = fetcher_logger("BeatmapRawFetcher")


class NoBeatmapError(Exception):
    """Beatmap 不存在异常"""

    pass


class BeatmapRawFetcher(BaseFetcher):
    def __init__(self, client_id: str = "", client_secret: str = "", **kwargs):
        # BeatmapRawFetcher 不需要 OAuth，传递空值给父类
        super().__init__(client_id, client_secret, **kwargs)
        # 使用共享的 HTTP 客户端和连接池
        self._client: AsyncClient | None = None
        # 用于并发请求去重
        self._pending_requests: dict[int, asyncio.Future[str]] = {}
        self._request_lock = asyncio.Lock()

    async def _get_client(self) -> AsyncClient:
        """获取或创建共享的 HTTP 客户端"""
        if self._client is None:
            # 配置连接池限制
            limits = Limits(
                max_keepalive_connections=20,
                max_connections=50,
                keepalive_expiry=30.0,
            )
            self._client = AsyncClient(
                timeout=10.0,  # 单个请求超时 10 秒
                limits=limits,
                follow_redirects=True,
            )
        return self._client

    async def close(self):
        """关闭 HTTP 客户端"""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def get_beatmap_raw(self, beatmap_id: int) -> str:
        future: asyncio.Future[str] | None = None

        # 检查是否已有正在进行的请求
        async with self._request_lock:
            if beatmap_id in self._pending_requests:
                logger.debug(f"Beatmap {beatmap_id} request already in progress, waiting...")
                future = self._pending_requests[beatmap_id]

        # 如果有正在进行的请求，等待它
        if future is not None:
            try:
                return await future
            except Exception as e:
                logger.warning(f"Waiting for beatmap {beatmap_id} failed: {e}")
                # 如果等待失败，继续自己发起请求
                future = None

        # 创建新的请求 Future
        async with self._request_lock:
            if beatmap_id in self._pending_requests:
                # 双重检查，可能在等待锁时已经有其他协程创建了
                future = self._pending_requests[beatmap_id]
                if future is not None:
                    try:
                        return await future
                    except Exception as e:
                        logger.debug(f"Concurrent request for beatmap {beatmap_id} failed: {e}")
                        # 继续创建新请求

            # 创建新的 Future
            future = asyncio.get_event_loop().create_future()
            self._pending_requests[beatmap_id] = future

        try:
            # 实际执行请求
            result = await self._fetch_beatmap_raw(beatmap_id)
            if not future.done():
                future.set_result(result)
            return result
        except asyncio.CancelledError:
            if not future.done():
                future.cancel()
            raise
        except Exception as e:
            if not future.done():
                future.set_exception(e)
            return await future
        finally:
            # 清理
            async with self._request_lock:
                self._pending_requests.pop(beatmap_id, None)

    async def _fetch_beatmap_raw(self, beatmap_id: int) -> str:
        client = await self._get_client()
        last_error = None

        for url_template in urls:
            req_url = url_template.format(beatmap_id=beatmap_id)
            try:
                logger.opt(colors=True).debug(f"get_beatmap_raw: <y>{req_url}</y>")
                resp = await client.get(req_url)

                if resp.status_code >= 400:
                    logger.warning(f"Beatmap {beatmap_id} from {req_url}: HTTP {resp.status_code}")
                    last_error = NoBeatmapError(f"HTTP {resp.status_code}")
                    continue

                if not resp.text:
                    logger.warning(f"Beatmap {beatmap_id} from {req_url}: empty response")
                    last_error = NoBeatmapError("Empty response")
                    continue

                logger.debug(f"Successfully fetched beatmap {beatmap_id} from {req_url}")
                return resp.text

            except Exception as e:
                logger.warning(f"Error fetching beatmap {beatmap_id} from {req_url}: {e}")
                last_error = e
                continue

        # 所有 URL 都失败了
        error_msg = f"Failed to fetch beatmap {beatmap_id} from all sources"
        if last_error and isinstance(last_error, NoBeatmapError):
            raise last_error
        raise HTTPError(error_msg) from last_error

    async def get_or_fetch_beatmap_raw(self, redis: redis.Redis, beatmap_id: int) -> str:
        from app.config import settings

        cache_key = f"beatmap:{beatmap_id}:raw"
        cache_expire = settings.beatmap_cache_expire_hours * 60 * 60

        # 检查缓存
        if await redis.exists(cache_key):
            content = await redis.get(cache_key)
            if content:
                # 延长缓存时间
                await redis.expire(cache_key, cache_expire)
                return content

        # 获取并缓存
        raw = await self.get_beatmap_raw(beatmap_id)
        await redis.set(cache_key, raw, ex=cache_expire)
        return raw
