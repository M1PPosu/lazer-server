from __future__ import annotations

from .beatmap import BeatmapFetcher
from .beatmapset import BeatmapsetFetcher


class Fetcher(BeatmapFetcher, BeatmapsetFetcher):
    """A class that combines all fetchers for easy access."""

    pass
