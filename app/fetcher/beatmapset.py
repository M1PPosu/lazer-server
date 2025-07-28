from __future__ import annotations

from app.database.beatmapset import BeatmapsetResp
from app.log import logger

from ._base import BaseFetcher

from httpx import AsyncClient


class BeatmapsetFetcher(BaseFetcher):
    async def get_beatmapset(self, beatmap_set_id: int) -> BeatmapsetResp:
        logger.opt(colors=True).debug(
            f"<blue>[BeatmapsetFetcher]</blue> get_beatmapset: <y>{beatmap_set_id}</y>"
        )
        async with AsyncClient() as client:
            response = await client.get(
                f"https://osu.ppy.sh/api/v2/beatmapsets/{beatmap_set_id}",
                headers=self.header,
            )
            response.raise_for_status()
            return BeatmapsetResp.model_validate(response.json())
