from __future__ import annotations

from ._base import BaseFetcher

from httpx import AsyncClient, HTTPError
from httpx._models import Response
from loguru import logger
import redis.asyncio as redis

urls = [
    "https://osu.ppy.sh/osu/{beatmap_id}",
    "https://osu.direct/api/osu/{beatmap_id}",
    "https://catboy.best/osu/{beatmap_id}",
]


class BeatmapRawFetcher(BaseFetcher):
    async def get_beatmap_raw(self, beatmap_id: int) -> str:
        for url in urls:
            req_url = url.format(beatmap_id=beatmap_id)
            logger.opt(colors=True).debug(
                f"<blue>[BeatmapRawFetcher]</blue> get_beatmap_raw: <y>{req_url}</y>"
            )
            resp = await self._request(req_url)
            if resp.status_code >= 400:
                continue
            return resp.text
        raise HTTPError("Failed to fetch beatmap")

    async def _request(self, url: str) -> Response:
        async with AsyncClient() as client:
            response = await client.get(
                url,
            )
            return response

    async def get_or_fetch_beatmap_raw(
        self, redis: redis.Redis, beatmap_id: int
    ) -> str:
        if await redis.exists(f"beatmap:{beatmap_id}:raw"):
            return await redis.get(f"beatmap:{beatmap_id}:raw")  # pyright: ignore[reportReturnType]
        raw = await self.get_beatmap_raw(beatmap_id)
        await redis.set(f"beatmap:{beatmap_id}:raw", raw, ex=60 * 60 * 24)
        return raw
