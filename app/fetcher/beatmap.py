from __future__ import annotations

from app.database.beatmap import BeatmapResp

from ._base import BaseFetcher

from httpx import AsyncClient


class BeatmapFetcher(BaseFetcher):
    async def get_beatmap(self, beatmap_id: int) -> BeatmapResp:
        async with AsyncClient() as client:
            response = await client.get(
                f"https://osu.ppy.sh/api/v2/beatmaps/{beatmap_id}",
                headers=self.header,
            )
            response.raise_for_status()
            return BeatmapResp.model_validate(response.json())
