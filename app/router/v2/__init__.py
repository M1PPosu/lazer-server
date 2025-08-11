from __future__ import annotations

from app.signalr import signalr_router as signalr_router

from . import (  # pyright: ignore[reportUnusedImport]  # noqa: F401
    beatmap,
    beatmapset,
    me,
    misc,
    relationship,
    room,
    score,
    user,
)
from .router import router as api_v2_router

__all__ = [
    "api_v2_router",
]
