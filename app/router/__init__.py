from __future__ import annotations

# from app.signalr import signalr_router as signalr_router
from .auth import router as auth_router
from .fetcher import fetcher_router as fetcher_router
from .file import file_router as file_router
from .lio import router as lio_router
from .notification import chat_router as chat_router
from .private import private_router as private_router
from .redirect import (
    redirect_api_router as redirect_api_router,
    redirect_router as redirect_router,
)
from .v1.router import router as api_v1_router
from .v2.router import router as api_v2_router

__all__ = [
    "api_v1_router",
    "api_v2_router",
    "auth_router",
    "chat_router",
    "fetcher_router",
    "file_router",
    "lio_router",
    "private_router",
    "redirect_api_router",
    "redirect_router",
    # "signalr_router",
]
