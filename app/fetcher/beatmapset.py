from __future__ import annotations

from app.database.beatmapset import BeatmapsetResp, SearchBeatmapsetsResp
from app.log import logger
from app.models.beatmap import SearchQueryModel
from app.models.model import Cursor

from ._base import BaseFetcher


class BeatmapsetFetcher(BaseFetcher):
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
        self, query: SearchQueryModel, cursor: Cursor
    ) -> SearchBeatmapsetsResp:
        logger.opt(colors=True).debug(
            f"<blue>[BeatmapsetFetcher]</blue> search_beatmapset: <y>{query}</y>"
        )

        params = query.model_dump(
            exclude_none=True, exclude_unset=True, exclude_defaults=True
        )
        for k, v in cursor.items():
            params[f"cursor[{k}]"] = v
        resp = SearchBeatmapsetsResp.model_validate(
            await self.request_api(
                "https://osu.ppy.sh/api/v2/beatmapsets/search",
                params=params,
            )
        )
        return resp
