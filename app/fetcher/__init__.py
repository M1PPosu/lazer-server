from __future__ import annotations

from .beatmap import BeatmapFetcher
from .beatmapset import BeatmapsetFetcher
from .osu_dot_direct import OsuDotDirectFetcher


class Fetcher(BeatmapFetcher, BeatmapsetFetcher, OsuDotDirectFetcher):
    """A class that combines all fetchers for easy access."""

    pass
