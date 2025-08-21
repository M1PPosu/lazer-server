from __future__ import annotations

import asyncio
import base64
import hashlib
import json

from app.database.beatmapset import BeatmapsetResp, SearchBeatmapsetsResp
from app.helpers.rate_limiter import osu_api_rate_limiter
from app.log import logger
from app.models.beatmap import SearchQueryModel
from app.models.model import Cursor

from ._base import BaseFetcher

import redis.asyncio as redis


class BeatmapsetFetcher(BaseFetcher):
    @staticmethod
    def _get_homepage_queries() -> list[tuple[SearchQueryModel, Cursor]]:
        """获取主页预缓存查询列表"""
        # 主页常用查询组合
        homepage_queries = []

        # 主要排序方式
        sorts = ["ranked_desc", "updated_desc", "favourites_desc", "plays_desc"]

        for sort in sorts:
            # 第一页 - 使用最小参数集合以匹配用户请求
            query = SearchQueryModel(
                q="",
                s="leaderboard",
                sort=sort,  # type: ignore
            )
            homepage_queries.append((query, {}))

        return homepage_queries

    async def request_api(self, url: str, method: str = "GET", **kwargs) -> dict:
        """覆盖基类方法，添加速率限制"""
        # 在请求前获取速率限制许可
        await osu_api_rate_limiter.acquire()

        # 调用基类的请求方法
        return await super().request_api(url, method, **kwargs)

    @staticmethod
    def _generate_cache_key(query: SearchQueryModel, cursor: Cursor) -> str:
        """生成搜索缓存键"""
        # 只包含核心查询参数，忽略默认值
        cache_data = {}

        # 添加非默认/非空的查询参数
        if query.q:
            cache_data["q"] = query.q
        if query.s != "leaderboard":  # 只有非默认值才加入
            cache_data["s"] = query.s
        if hasattr(query, "sort") and query.sort:
            cache_data["sort"] = query.sort
        if query.nsfw is not False:  # 只有非默认值才加入
            cache_data["nsfw"] = query.nsfw
        if query.m is not None:
            cache_data["m"] = query.m
        if query.c:
            cache_data["c"] = query.c
        if query.l != "any":  # 检查语言默认值
            cache_data["l"] = query.l
        if query.e:
            cache_data["e"] = query.e
        if query.r:
            cache_data["r"] = query.r
        if query.played is not False:
            cache_data["played"] = query.played

        # 添加 cursor
        if cursor:
            cache_data["cursor"] = cursor

        # 序列化为 JSON 并生成 MD5 哈希
        cache_json = json.dumps(cache_data, sort_keys=True, separators=(",", ":"))
        cache_hash = hashlib.md5(cache_json.encode()).hexdigest()

        logger.opt(colors=True).debug(
            f"<blue>[CacheKey]</blue> Query: {cache_data}, Hash: {cache_hash}"
        )

        return f"beatmapset:search:{cache_hash}"

    @staticmethod
    def _encode_cursor(cursor_dict: dict[str, int | float]) -> str:
        """将cursor字典编码为base64字符串"""
        cursor_json = json.dumps(cursor_dict, separators=(",", ":"))
        return base64.b64encode(cursor_json.encode()).decode()

    @staticmethod
    def _decode_cursor(cursor_string: str) -> dict[str, int | float]:
        """将base64字符串解码为cursor字典"""
        try:
            cursor_json = base64.b64decode(cursor_string).decode()
            return json.loads(cursor_json)
        except Exception:
            return {}

    async def get_beatmapset(self, beatmap_set_id: int) -> BeatmapsetResp:
        logger.opt(colors=True).debug(
            f"<blue>[BeatmapsetFetcher]</blue> get_beatmapset: <y>{beatmap_set_id}</y>"
        )

        return BeatmapsetResp.model_validate(
            await self.request_api(
                f"https://osu.ppy.sh/api/v2/beatmapsets/{beatmap_set_id}"
            )
        )

    async def search_beatmapset(
        self, query: SearchQueryModel, cursor: Cursor, redis_client: redis.Redis
    ) -> SearchBeatmapsetsResp:
        logger.opt(colors=True).debug(
            f"<blue>[BeatmapsetFetcher]</blue> search_beatmapset: <y>{query}</y>"
        )

        # 生成缓存键
        cache_key = self._generate_cache_key(query, cursor)

        # 尝试从缓存获取结果
        cached_result = await redis_client.get(cache_key)
        if cached_result:
            logger.opt(colors=True).debug(
                f"<green>[BeatmapsetFetcher]</green> Cache hit for key: <y>{cache_key}</y>"
            )
            try:
                cached_data = json.loads(cached_result)
                return SearchBeatmapsetsResp.model_validate(cached_data)
            except Exception as e:
                logger.opt(colors=True).warning(
                    f"<yellow>[BeatmapsetFetcher]</yellow> Cache data invalid, fetching from API: {e}"
                )

        # 缓存未命中，从 API 获取数据
        logger.opt(colors=True).debug(
            "<blue>[BeatmapsetFetcher]</blue> Cache miss, fetching from API"
        )

        params = query.model_dump(
            exclude_none=True, exclude_unset=True, exclude_defaults=True
        )

        if query.cursor_string:
            params["cursor_string"] = query.cursor_string
        else:
            for k, v in cursor.items():
                params[f"cursor[{k}]"] = v

        api_response = await self.request_api(
            "https://osu.ppy.sh/api/v2/beatmapsets/search",
            params=params,
        )

        # 处理响应中的cursor信息
        if api_response.get("cursor"):
            cursor_dict = api_response["cursor"]
            api_response["cursor_string"] = self._encode_cursor(cursor_dict)

        # 将结果缓存 15 分钟
        cache_ttl = 15 * 60  # 15 分钟
        await redis_client.set(
            cache_key, json.dumps(api_response, separators=(",", ":")), ex=cache_ttl
        )

        logger.opt(colors=True).debug(
            f"<green>[BeatmapsetFetcher]</green> Cached result for key: "
            f"<y>{cache_key}</y> (TTL: {cache_ttl}s)"
        )

        resp = SearchBeatmapsetsResp.model_validate(api_response)

        # 智能预取：只在用户明确搜索时才预取，避免过多API请求
        # 且只在有搜索词或特定条件时预取，避免首页浏览时的过度预取
        if api_response.get("cursor") and (
            query.q or query.s != "leaderboard" or cursor
        ):
            # 在后台预取下1页（减少预取量）
            import asyncio

            # 不立即创建任务，而是延迟一段时间再预取
            async def delayed_prefetch():
                await asyncio.sleep(3.0)  # 延迟3秒
                await self.prefetch_next_pages(
                    query, api_response["cursor"], redis_client, pages=1
                )

            # 创建延迟预取任务
            task = asyncio.create_task(delayed_prefetch())
            # 添加到后台任务集合避免被垃圾回收
            if not hasattr(self, "_background_tasks"):
                self._background_tasks = set()
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)

        return resp

    async def prefetch_next_pages(
        self,
        query: SearchQueryModel,
        current_cursor: Cursor,
        redis_client: redis.Redis,
        pages: int = 3,
    ) -> None:
        """预取下几页内容"""
        if not current_cursor:
            return

        try:
            cursor = current_cursor.copy()

            for page in range(1, pages + 1):
                # 使用当前 cursor 请求下一页
                next_query = query.model_copy()

                logger.opt(colors=True).debug(
                    f"<cyan>[BeatmapsetFetcher]</cyan> Prefetching page {page + 1}"
                )

                # 生成下一页的缓存键
                next_cache_key = self._generate_cache_key(next_query, cursor)

                # 检查是否已经缓存
                if await redis_client.exists(next_cache_key):
                    logger.opt(colors=True).debug(
                        f"<cyan>[BeatmapsetFetcher]</cyan> Page {page + 1} already cached"
                    )
                    # 尝试从缓存获取cursor继续预取
                    cached_data = await redis_client.get(next_cache_key)
                    if cached_data:
                        try:
                            data = json.loads(cached_data)
                            if data.get("cursor"):
                                cursor = data["cursor"]
                                continue
                        except Exception:
                            pass
                    break

                # 在预取页面之间添加延迟，避免突发请求
                if page > 1:
                    await asyncio.sleep(1.5)  # 1.5秒延迟

                # 请求下一页数据
                params = next_query.model_dump(
                    exclude_none=True, exclude_unset=True, exclude_defaults=True
                )

                for k, v in cursor.items():
                    params[f"cursor[{k}]"] = v

                api_response = await self.request_api(
                    "https://osu.ppy.sh/api/v2/beatmapsets/search",
                    params=params,
                )

                # 处理响应中的cursor信息
                if api_response.get("cursor"):
                    cursor_dict = api_response["cursor"]
                    api_response["cursor_string"] = self._encode_cursor(cursor_dict)
                    cursor = cursor_dict  # 更新cursor用于下一页
                else:
                    # 没有更多页面了
                    break

                # 缓存结果（较短的TTL用于预取）
                prefetch_ttl = 10 * 60  # 10 分钟
                await redis_client.set(
                    next_cache_key,
                    json.dumps(api_response, separators=(",", ":")),
                    ex=prefetch_ttl,
                )

                logger.opt(colors=True).debug(
                    f"<cyan>[BeatmapsetFetcher]</cyan> Prefetched page {page + 1} "
                    f"(TTL: {prefetch_ttl}s)"
                )

        except Exception as e:
            logger.opt(colors=True).warning(
                f"<yellow>[BeatmapsetFetcher]</yellow> Prefetch failed: {e}"
            )

    async def warmup_homepage_cache(self, redis_client: redis.Redis) -> None:
        """预热主页缓存"""
        homepage_queries = self._get_homepage_queries()

        logger.opt(colors=True).info(
            f"<magenta>[BeatmapsetFetcher]</magenta> Starting homepage cache warmup "
            f"({len(homepage_queries)} queries)"
        )

        for i, (query, cursor) in enumerate(homepage_queries):
            try:
                # 在请求之间添加延迟，避免突发请求
                if i > 0:
                    await asyncio.sleep(2.0)  # 2秒延迟

                cache_key = self._generate_cache_key(query, cursor)

                # 检查是否已经缓存
                if await redis_client.exists(cache_key):
                    logger.opt(colors=True).debug(
                        f"<magenta>[BeatmapsetFetcher]</magenta> "
                        f"Query {query.sort} already cached"
                    )
                    continue

                # 请求并缓存
                params = query.model_dump(
                    exclude_none=True, exclude_unset=True, exclude_defaults=True
                )

                api_response = await self.request_api(
                    "https://osu.ppy.sh/api/v2/beatmapsets/search",
                    params=params,
                )

                if api_response.get("cursor"):
                    cursor_dict = api_response["cursor"]
                    api_response["cursor_string"] = self._encode_cursor(cursor_dict)

                # 缓存结果
                cache_ttl = 20 * 60  # 20 分钟
                await redis_client.set(
                    cache_key,
                    json.dumps(api_response, separators=(",", ":")),
                    ex=cache_ttl,
                )

                logger.opt(colors=True).info(
                    f"<magenta>[BeatmapsetFetcher]</magenta> "
                    f"Warmed up cache for {query.sort} (TTL: {cache_ttl}s)"
                )

                if api_response.get("cursor"):
                    await self.prefetch_next_pages(
                        query, api_response["cursor"], redis_client, pages=2
                    )

            except Exception as e:
                logger.opt(colors=True).error(
                    f"<red>[BeatmapsetFetcher]</red> "
                    f"Failed to warmup cache for {query.sort}: {e}"
                )
