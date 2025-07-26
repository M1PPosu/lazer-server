from __future__ import annotations

from typing import TYPE_CHECKING

from ._base import BaseFetcher

from httpx import AsyncClient

if TYPE_CHECKING:
    from app.database.beatmap import BeatmapResp


class BeatmapFetcher(BaseFetcher):
    async def get_beatmap(self, beatmap_id: int) -> "BeatmapResp":
        from app.database.beatmap import BeatmapResp

        async with AsyncClient() as client:
            response = await client.get(
                f"https://osu.ppy.sh/api/v2/beatmaps/{beatmap_id}",
                headers=self.header,
            )
            response.raise_for_status()
            return BeatmapResp.model_validate(response.json())
