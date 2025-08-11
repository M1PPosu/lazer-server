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
from .api_router import router as api_router
from .auth import router as auth_router
from .fetcher import fetcher_router as fetcher_router

__all__ = [
    "api_router",
    "auth_router",
    "fetcher_router",
    "signalr_router",
]
