from __future__ import annotations

from ._base import BaseFetcher

from httpx import AsyncClient
from loguru import logger


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
