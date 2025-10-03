from __future__ import annotations

from datetime import datetime, timedelta

from app.dependencies.scheduler import get_scheduler
from app.service.beatmapset_update_service import get_beatmapset_update_service
from app.utils import bg_tasks

SCHEDULER_INTERVAL_MINUTES = 2


@get_scheduler().scheduled_job(
    "interval",
    id="update_beatmaps",
    minutes=SCHEDULER_INTERVAL_MINUTES,
    next_run_time=datetime.now() + timedelta(minutes=1),
)
async def beatmapset_update_job():
    service = get_beatmapset_update_service()
    bg_tasks.add_task(service.add_missing_beatmapsets)
    await service._update_beatmaps()
