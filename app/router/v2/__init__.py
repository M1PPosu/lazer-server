from __future__ import annotations

from . import (  # pyright: ignore[reportUnusedImport]  # noqa: F401
    beatmap,
    beatmapset,
    me,
    misc,
    ranking,
    relationship,
    room,
    score,
    user,
)
from .router import router as api_v2_router

__all__ = [
    "api_v2_router",
]
