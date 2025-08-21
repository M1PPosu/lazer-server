from __future__ import annotations

import asyncio
from datetime import datetime

from app.log import logger
from app.router.v2.stats import record_hourly_stats, update_registered_users_count


class StatsScheduler:
    """统计数据调度器"""
    
    def __init__(self):
        self._running = False
        self._stats_task: asyncio.Task | None = None
        self._registered_task: asyncio.Task | None = None
    
    def start(self) -> None:
        """启动调度器"""
        if self._running:
            return
            
        self._running = True
        self._stats_task = asyncio.create_task(self._stats_loop())
        self._registered_task = asyncio.create_task(self._registered_users_loop())
        logger.info("Stats scheduler started")
    
    def stop(self) -> None:
        """停止调度器"""
        if not self._running:
            return
            
        self._running = False
        
        if self._stats_task:
            self._stats_task.cancel()
        if self._registered_task:
            self._registered_task.cancel()
            
        logger.info("Stats scheduler stopped")
    
    async def _stats_loop(self) -> None:
        """统计数据记录循环 - 每30分钟记录一次"""
        while self._running:
            try:
                await record_hourly_stats()
                logger.debug("Recorded hourly statistics")
            except Exception as e:
                logger.error(f"Error in stats loop: {e}")
            
            # 等待30分钟
            await asyncio.sleep(30 * 60)
    
    async def _registered_users_loop(self) -> None:
        """注册用户数更新循环 - 每5分钟更新一次"""
        while self._running:
            try:
                await update_registered_users_count()
                logger.debug("Updated registered users count")
            except Exception as e:
                logger.error(f"Error in registered users loop: {e}")
            
            # 等待5分钟
            await asyncio.sleep(5 * 60)


# 全局调度器实例
stats_scheduler = StatsScheduler()


def start_stats_scheduler() -> None:
    """启动统计调度器"""
    stats_scheduler.start()


def stop_stats_scheduler() -> None:
    """停止统计调度器"""
    stats_scheduler.stop()
