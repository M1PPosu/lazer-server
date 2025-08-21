from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from app.log import logger
from app.router.v2.stats import record_hourly_stats, update_registered_users_count
from app.service.stats_cleanup import cleanup_stale_online_users, refresh_redis_key_expiry
from app.service.enhanced_interval_stats import EnhancedIntervalStatsManager


class StatsScheduler:
    """统计数据调度器"""
    
    def __init__(self):
        self._running = False
        self._stats_task: asyncio.Task | None = None
        self._registered_task: asyncio.Task | None = None
        self._cleanup_task: asyncio.Task | None = None
    
    def start(self) -> None:
        """启动调度器"""
        if self._running:
            return
            
        self._running = True
        self._stats_task = asyncio.create_task(self._stats_loop())
        self._registered_task = asyncio.create_task(self._registered_users_loop())
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
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
        if self._cleanup_task:
            self._cleanup_task.cancel()
            
        logger.info("Stats scheduler stopped")
    
    async def _stats_loop(self) -> None:
        """统计数据记录循环 - 每30分钟记录一次"""
        # 启动时立即记录一次统计数据
        try:
            await EnhancedIntervalStatsManager.initialize_current_interval()
            logger.info("Initial enhanced interval statistics initialized on startup")
        except Exception as e:
            logger.error(f"Error initializing enhanced interval stats: {e}")
        
        while self._running:
            try:
                # 计算下次记录时间（下个30分钟整点）
                now = datetime.utcnow()
                
                # 计算当前区间边界
                current_minute = (now.minute // 30) * 30
                current_interval_end = now.replace(minute=current_minute, second=0, microsecond=0) + timedelta(minutes=30)
                
                # 如果已经过了当前区间结束时间，立即处理
                if now >= current_interval_end:
                    current_interval_end += timedelta(minutes=30)
                
                # 计算需要等待的时间（到下个区间结束）
                sleep_seconds = (current_interval_end - now).total_seconds()
                
                # 确保至少等待1分钟，最多等待31分钟
                sleep_seconds = max(min(sleep_seconds, 31 * 60), 60)
                
                logger.debug(f"Next interval finalization in {sleep_seconds/60:.1f} minutes at {current_interval_end.strftime('%H:%M:%S')}")
                await asyncio.sleep(sleep_seconds)
                
                if not self._running:
                    break
                
                # 完成当前区间并记录到历史
                finalized_stats = await EnhancedIntervalStatsManager.finalize_interval()
                if finalized_stats:
                    logger.info(f"Finalized enhanced interval statistics at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")
                else:
                    # 如果区间完成失败，使用原有方式记录
                    await record_hourly_stats()
                    logger.info(f"Recorded hourly statistics (fallback) at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")
                
                # 开始新的区间统计
                await EnhancedIntervalStatsManager.initialize_current_interval()
                
            except Exception as e:
                logger.error(f"Error in stats loop: {e}")
                # 出错时等待5分钟再重试
                await asyncio.sleep(5 * 60)
    
    async def _registered_users_loop(self) -> None:
        """注册用户数更新循环 - 每5分钟更新一次"""
        # 启动时立即更新一次注册用户数
        try:
            await update_registered_users_count()
            logger.info("Initial registered users count updated on startup")
        except Exception as e:
            logger.error(f"Error updating initial registered users count: {e}")
            
        while self._running:
            # 等待5分钟
            await asyncio.sleep(5 * 60)
            
            if not self._running:
                break
                
            try:
                await update_registered_users_count()
                logger.debug("Updated registered users count")
            except Exception as e:
                logger.error(f"Error in registered users loop: {e}")

    async def _cleanup_loop(self) -> None:
        """清理循环 - 每10分钟清理一次过期用户"""
        # 启动时立即执行一次清理
        try:
            online_cleaned, playing_cleaned = await cleanup_stale_online_users()
            if online_cleaned > 0 or playing_cleaned > 0:
                logger.info(f"Initial cleanup: removed {online_cleaned} stale online users, {playing_cleaned} stale playing users")
            
            await refresh_redis_key_expiry()
        except Exception as e:
            logger.error(f"Error in initial cleanup: {e}")
            
        while self._running:
            # 等待10分钟
            await asyncio.sleep(10 * 60)
            
            if not self._running:
                break
                
            try:
                # 清理过期用户
                online_cleaned, playing_cleaned = await cleanup_stale_online_users()
                if online_cleaned > 0 or playing_cleaned > 0:
                    logger.info(f"Cleanup: removed {online_cleaned} stale online users, {playing_cleaned} stale playing users")
                
                # 刷新Redis key过期时间
                await refresh_redis_key_expiry()
                
                # 清理过期的区间数据
                await EnhancedIntervalStatsManager.cleanup_old_intervals()
                
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
                # 出错时等待2分钟再重试
                await asyncio.sleep(2 * 60)


# 全局调度器实例
stats_scheduler = StatsScheduler()


def start_stats_scheduler() -> None:
    """启动统计调度器"""
    stats_scheduler.start()


def stop_stats_scheduler() -> None:
    """停止统计调度器"""
    stats_scheduler.stop()
