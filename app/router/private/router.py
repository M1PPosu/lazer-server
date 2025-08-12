from __future__ import annotations

from app.config import settings

from fastapi import APIRouter

router = APIRouter(
    prefix="/api/private",
    include_in_schema=settings.debug,
    tags=["私有 API"],
)
