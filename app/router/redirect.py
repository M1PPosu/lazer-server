from __future__ import annotations

import urllib.parse

from app.config import settings

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

redirect_router = APIRouter(include_in_schema=False)


@redirect_router.get("/users/{user_id}")
@redirect_router.get("/u/{user_id}")
@redirect_router.get("/b/{beatmap_id}")
@redirect_router.get("/s/{beatmapset_id}")
@redirect_router.get("/beatmapsets/{path:path}")
@redirect_router.get("/multiplayer/rooms/{room_id}")
@redirect_router.get("/oauth/authorize")
async def redirect(request: Request):
    query_string = request.url.query
    target_path = request.url.path
    redirect_url = urllib.parse.urljoin(str(settings.frontend_url), target_path)
    if query_string:
        redirect_url = f"{redirect_url}?{query_string}"

    return RedirectResponse(
        redirect_url,
        status_code=301,
    )
