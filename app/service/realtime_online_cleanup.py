"""
实时在线状态清理服务

此模块提供实时的在线状态清理功能，确保用户在断开连接后立即从在线列表中移除。
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta

from app.dependencies.database import get_redis, get_redis_message
from app.log import logger
from app.router.v2.stats import (
    REDIS_ONLINE_USERS_KEY,
    REDIS_PLAYING_USERS_KEY,
    _redis_exec,
)


class RealtimeOnlineCleanup:
    """实时在线状态清理器"""
    
    def __init__(self):
        self._running = False
        self._task = None
        
    async def start(self):
        """启动实时清理服务"""
        if self._running:
            return
            
        self._running = True
        self._task = asyncio.create_task(self._realtime_cleanup_loop())
        logger.info("[RealtimeOnlineCleanup] Started realtime online cleanup service")
        
    async def stop(self):
        """停止实时清理服务"""
        if not self._running:
            return
            
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("[RealtimeOnlineCleanup] Stopped realtime online cleanup service")
        
    async def _realtime_cleanup_loop(self):
        """实时清理循环 - 每30秒检查一次"""
        while self._running:
            try:
                # 执行快速清理
                cleaned_count = await self._quick_cleanup_stale_users()
                if cleaned_count > 0:
                    logger.debug(f"[RealtimeOnlineCleanup] Quick cleanup: removed {cleaned_count} stale users")
                
                # 等待30秒
                await asyncio.sleep(30)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[RealtimeOnlineCleanup] Error in cleanup loop: {e}")
                # 出错时等待30秒再重试
                await asyncio.sleep(30)
    
    async def _quick_cleanup_stale_users(self) -> int:
        """快速清理过期用户，返回清理数量"""
        redis_sync = get_redis_message()
        redis_async = get_redis()
        
        total_cleaned = 0
        
        try:
            # 获取所有在线用户
            online_users = await _redis_exec(redis_sync.smembers, REDIS_ONLINE_USERS_KEY)
            
            # 快速检查：只检查metadata键是否存在
            stale_users = []
            for user_id in online_users:
                user_id_str = user_id.decode() if isinstance(user_id, bytes) else str(user_id)
                metadata_key = f"metadata:online:{user_id_str}"
                
                # 如果metadata标记不存在，立即标记为过期
                if not await redis_async.exists(metadata_key):
                    stale_users.append(user_id_str)
            
            # 立即清理过期用户
            if stale_users:
                # 从在线用户集合中移除
                await _redis_exec(redis_sync.srem, REDIS_ONLINE_USERS_KEY, *stale_users)
                # 同时从游玩用户集合中移除（如果存在）
                await _redis_exec(redis_sync.srem, REDIS_PLAYING_USERS_KEY, *stale_users)
                total_cleaned = len(stale_users)
                
                logger.info(f"[RealtimeOnlineCleanup] Immediately cleaned {total_cleaned} stale users")
        
        except Exception as e:
            logger.error(f"[RealtimeOnlineCleanup] Error in quick cleanup: {e}")
            
        return total_cleaned
    
    async def verify_user_online_status(self, user_id: int) -> bool:
        """实时验证用户在线状态"""
        try:
            redis = get_redis()
            metadata_key = f"metadata:online:{user_id}"
            
            # 检查metadata键是否存在
            exists = await redis.exists(metadata_key)
            
            # 如果不存在，从在线集合中移除该用户
            if not exists:
                redis_sync = get_redis_message()
                await _redis_exec(redis_sync.srem, REDIS_ONLINE_USERS_KEY, str(user_id))
                await _redis_exec(redis_sync.srem, REDIS_PLAYING_USERS_KEY, str(user_id))
                logger.debug(f"[RealtimeOnlineCleanup] Verified user {user_id} is offline, removed from sets")
                
            return bool(exists)
            
        except Exception as e:
            logger.error(f"[RealtimeOnlineCleanup] Error verifying user {user_id} status: {e}")
            return False
    
    async def force_refresh_online_list(self):
        """强制刷新整个在线用户列表"""
        try:
            redis_sync = get_redis_message()
            redis_async = get_redis()
            
            # 获取所有在线用户
            online_users = await _redis_exec(redis_sync.smembers, REDIS_ONLINE_USERS_KEY)
            playing_users = await _redis_exec(redis_sync.smembers, REDIS_PLAYING_USERS_KEY)
            
            # 验证每个用户的在线状态
            valid_online_users = []
            valid_playing_users = []
            
            for user_id in online_users:
                user_id_str = user_id.decode() if isinstance(user_id, bytes) else str(user_id)
                metadata_key = f"metadata:online:{user_id_str}"
                
                if await redis_async.exists(metadata_key):
                    valid_online_users.append(user_id_str)
            
            for user_id in playing_users:
                user_id_str = user_id.decode() if isinstance(user_id, bytes) else str(user_id)
                metadata_key = f"metadata:online:{user_id_str}"
                
                if await redis_async.exists(metadata_key):
                    valid_playing_users.append(user_id_str)
            
            # 重建在线用户集合
            if online_users:
                await _redis_exec(redis_sync.delete, REDIS_ONLINE_USERS_KEY)
                if valid_online_users:
                    await _redis_exec(redis_sync.sadd, REDIS_ONLINE_USERS_KEY, *valid_online_users)
                    # 设置过期时间
                    await redis_async.expire(REDIS_ONLINE_USERS_KEY, 3 * 3600)
            
            # 重建游玩用户集合
            if playing_users:
                await _redis_exec(redis_sync.delete, REDIS_PLAYING_USERS_KEY)
                if valid_playing_users:
                    await _redis_exec(redis_sync.sadd, REDIS_PLAYING_USERS_KEY, *valid_playing_users)
                    # 设置过期时间
                    await redis_async.expire(REDIS_PLAYING_USERS_KEY, 3 * 3600)
            
            cleaned_online = len(online_users) - len(valid_online_users)
            cleaned_playing = len(playing_users) - len(valid_playing_users)
            
            if cleaned_online > 0 or cleaned_playing > 0:
                logger.info(f"[RealtimeOnlineCleanup] Force refresh: removed {cleaned_online} stale online users, {cleaned_playing} stale playing users")
            
            return cleaned_online + cleaned_playing
            
        except Exception as e:
            logger.error(f"[RealtimeOnlineCleanup] Error in force refresh: {e}")
            return 0


# 全局实例
realtime_cleanup = RealtimeOnlineCleanup()


def start_realtime_cleanup():
    """启动实时清理服务"""
    asyncio.create_task(realtime_cleanup.start())


def stop_realtime_cleanup():
    """停止实时清理服务"""
    asyncio.create_task(realtime_cleanup.stop())
