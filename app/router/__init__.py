from __future__ import annotations

from app.signalr import signalr_router as signalr_router

from .auth import router as auth_router
from .fetcher import fetcher_router as fetcher_router
from .v2 import api_v2_router as api_v2_router

__all__ = ["api_v2_router", "auth_router", "fetcher_router", "signalr_router"]
