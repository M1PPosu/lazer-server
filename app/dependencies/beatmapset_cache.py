from __future__ import annotations

from typing import Annotated

from app.dependencies.database import Redis
from app.service.beatmapset_cache_service import (
    BeatmapsetCacheService as OriginBeatmapsetCacheService,
    get_beatmapset_cache_service,
)

from fastapi import Depends


def get_beatmapset_cache_dependency(redis: Redis) -> OriginBeatmapsetCacheService:
    """获取beatmapset缓存服务依赖"""
    return get_beatmapset_cache_service(redis)


BeatmapsetCacheService = Annotated[OriginBeatmapsetCacheService, Depends(get_beatmapset_cache_dependency)]
