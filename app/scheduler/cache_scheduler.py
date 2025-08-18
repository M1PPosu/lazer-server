from __future__ import annotations

import asyncio

from app.dependencies.database import get_redis
from app.dependencies.fetcher import get_fetcher
from app.log import logger


class BeatmapsetCacheScheduler:
    """谱面集缓存调度器"""

    def __init__(self):
        self.running = False
        self.task = None

    async def start(self):
        """启动调度器"""
        if self.running:
            return

        self.running = True
        self.task = asyncio.create_task(self._run_scheduler())
        logger.info("BeatmapsetCacheScheduler started")

    async def stop(self):
        """停止调度器"""
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("BeatmapsetCacheScheduler stopped")

    async def _run_scheduler(self):
        """运行调度器主循环"""
        # 启动时立即执行一次预热
        await self._warmup_cache()

        while self.running:
            try:
                # 每30分钟执行一次缓存预热
                await asyncio.sleep(30 * 60)  # 30分钟

                if self.running:
                    await self._warmup_cache()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cache scheduler error: {e}")
                await asyncio.sleep(60)  # 出错后等待1分钟再继续

    async def _warmup_cache(self):
        """执行缓存预热"""
        try:
            logger.info("Starting cache warmup...")

            fetcher = await get_fetcher()
            redis = get_redis()

            # 预热主页缓存
            await fetcher.warmup_homepage_cache(redis)

            logger.info("Cache warmup completed successfully")

        except Exception as e:
            logger.error(f"Cache warmup failed: {e}")


# 全局调度器实例
cache_scheduler = BeatmapsetCacheScheduler()


async def start_cache_scheduler():
    """启动缓存调度器"""
    await cache_scheduler.start()


async def stop_cache_scheduler():
    """停止缓存调度器"""
    await cache_scheduler.stop()
