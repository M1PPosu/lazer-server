from __future__ import annotations

from app.database.beatmap import BeatmapResp
from app.log import logger

from ._base import BaseFetcher

from httpx import AsyncClient


class BeatmapFetcher(BaseFetcher):
    async def get_beatmap(
        self, beatmap_id: int | None = None, beatmap_checksum: str | None = None
    ) -> BeatmapResp:
        if beatmap_id:
            params = {"id": beatmap_id}
        elif beatmap_checksum:
            params = {"checksum": beatmap_checksum}
        else:
            raise ValueError("Either beatmap_id or beatmap_checksum must be provided.")
        logger.opt(colors=True).debug(
            f"<blue>[BeatmapFetcher]</blue> get_beatmap: <y>{params}</y>"
        )
        async with AsyncClient() as client:
            response = await client.get(
                "https://osu.ppy.sh/api/v2/beatmaps/lookup",
                headers=self.header,
                params=params,
            )
            response.raise_for_status()
            return BeatmapResp.model_validate(response.json())
