"""
Scheduled Update Service
Periodically update the MaxMind GeoIP database
"""

from __future__ import annotations

import asyncio

from app.config import settings
from app.dependencies.geoip import get_geoip_helper
from app.dependencies.scheduler import get_scheduler
from app.log import logger


@get_scheduler().scheduled_job(
    "cron",
    day_of_week=settings.geoip_update_day,
    hour=settings.geoip_update_hour,
    minute=0,
    id="geoip_weekly_update",
    name="Weekly GeoIP database update",
)
async def update_geoip_database():
    """
    Asynchronous task to update the GeoIP database
    """
    try:
        logger.info("Starting scheduled GeoIP database update...")
        geoip = get_geoip_helper()

        # Run the synchronous update method in a background thread
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: geoip.update(force=False))

        logger.info("Scheduled GeoIP database update completed successfully")
    except Exception as e:
        logger.error(f"Scheduled GeoIP database update failed: {e}")


async def init_geoip():
    """
    Asynchronously initialize the GeoIP database
    """
    try:
        geoip = get_geoip_helper()
        logger.info("Initializing GeoIP database...")

        # Run the synchronous update method in a background thread
        # force=False means only download if files don't exist or are expired
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: geoip.update(force=False))

        logger.info("GeoIP database initialization completed")
    except Exception as e:
        logger.error(f"GeoIP database initialization failed: {e}")
        # Do not raise an exception to avoid blocking application startup
