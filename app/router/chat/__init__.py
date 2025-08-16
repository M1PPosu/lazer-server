from __future__ import annotations

from app.config import settings
from app.router.v2 import api_v2_router as router

from . import channel, message  # noqa: F401
from .server import chat_router as chat_router

from fastapi import Query

__all__ = ["chat_router"]


@router.get("/notifications")
async def get_notifications(max_id: int | None = Query(None)):
    if settings.server_url is not None:
        notification_endpoint = f"{settings.server_url}notification-server".replace(
            "http://", "ws://"
        ).replace("https://", "wss://")
    else:
        notification_endpoint = "/notification-server"

    return {
        "has_more": False,
        "notifications": [],
        "unread_count": 0,
        "notification_endpoint": notification_endpoint,
    }
