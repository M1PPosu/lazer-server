from __future__ import annotations

from . import beatmap, replay, score, user  # noqa: F401
from .router import router as api_v1_router

__all__ = ["api_v1_router"]
