from __future__ import annotations

from . import beatmap, replay, score, user, public_user  # noqa: F401
from .router import router as api_v1_router
from .public_router import public_router as api_v1_public_router

__all__ = ["api_v1_router", "api_v1_public_router"]
