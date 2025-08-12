from __future__ import annotations

from app.signalr import signalr_router as signalr_router

from .auth import router as auth_router
from .fetcher import fetcher_router as fetcher_router
from .file import file_router as file_router
from .private import private_router as private_router
from .redirect import redirect_router as redirect_router
from .v2.router import router as api_v2_router

__all__ = [
    "api_v2_router",
    "auth_router",
    "fetcher_router",
    "file_router",
    "private_router",
    "redirect_router",
    "signalr_router",
]
