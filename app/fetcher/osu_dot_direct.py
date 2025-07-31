from __future__ import annotations

from ._base import BaseFetcher

from httpx import AsyncClient
from loguru import logger
import redis.asyncio as redis


class OsuDotDirectFetcher(BaseFetcher):
    async def get_beatmap_raw(self, beatmap_id: int) -> str:
        logger.opt(colors=True).debug(
            f"<blue>[OsuDotDirectFetcher]</blue> get_beatmap_raw: <y>{beatmap_id}</y>"
        )
        async with AsyncClient() as client:
            response = await client.get(
                f"https://osu.direct/api/osu/{beatmap_id}/raw",
            )
            response.raise_for_status()
            return response.text

    async def get_or_fetch_beatmap_raw(
        self, redis: redis.Redis, beatmap_id: int
    ) -> str:
        if redis.exists(f"beatmap:{beatmap_id}:raw"):
            return await redis.get(f"beatmap:{beatmap_id}:raw")  # pyright: ignore[reportReturnType]
        raw = await self.get_beatmap_raw(beatmap_id)
        await redis.set(f"beatmap:{beatmap_id}:raw", raw, ex=60 * 60 * 24)
        return raw
