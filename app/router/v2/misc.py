from __future__ import annotations

from datetime import UTC, datetime

from app.config import settings

from .router import router

from pydantic import BaseModel


class Background(BaseModel):
    url: str


class BackgroundsResp(BaseModel):
    ends_at: datetime = datetime(year=9999, month=12, day=31, tzinfo=UTC)
    backgrounds: list[Background]


@router.get("/seasonal-backgrounds", response_model=BackgroundsResp)
async def get_seasonal_backgrounds():
    return BackgroundsResp(
        backgrounds=[Background(url=url) for url in settings.seasonal_backgrounds]
    )
