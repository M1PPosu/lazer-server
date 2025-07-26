from __future__ import annotations

from app.database.beatmapset import BeatmapsetResp

from ._base import BaseFetcher

from httpx import AsyncClient


class BeatmapsetFetcher(BaseFetcher):
    async def get_beatmapset(self, beatmap_set_id: int) -> BeatmapsetResp:
        async with AsyncClient() as client:
            response = await client.get(
                f"https://osu.ppy.sh/api/v2/beatmapsets/{beatmap_set_id}",
                headers=self.header,
            )
            response.raise_for_status()
            return BeatmapsetResp.model_validate(response.json())
