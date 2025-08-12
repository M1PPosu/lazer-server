from __future__ import annotations

from datetime import UTC

from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler: AsyncIOScheduler | None = None


def init_scheduler():
    global scheduler
    scheduler = AsyncIOScheduler(timezone=UTC)
    scheduler.start()


def get_scheduler() -> AsyncIOScheduler:
    global scheduler
    if scheduler is None:
        init_scheduler()
    return scheduler  # pyright: ignore[reportReturnType]


def stop_scheduler():
    global scheduler
    if scheduler:
        scheduler.shutdown()
