from __future__ import annotations

from ._base import BaseFetcher

from httpx import AsyncClient


class OsuDotDirectFetcher(BaseFetcher):
    async def get_beatmap_raw(self, beatmap_id: int) -> str:
        async with AsyncClient() as client:
            response = await client.get(
                f"https://osu.direct/api/osu/{beatmap_id}/raw",
            )
            response.raise_for_status()
            return response.text
