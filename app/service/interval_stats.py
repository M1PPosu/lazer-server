from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Dict, Optional

from app.dependencies.database import get_redis, get_redis_message
from app.log import logger
from app.router.v2.stats import (
    REDIS_ONLINE_HISTORY_KEY,
    _get_online_users_count,
    _get_playing_users_count,
    _redis_exec
)

# Redis key for current interval stats
CURRENT_INTERVAL_STATS_KEY = "server:current_interval_stats"

class IntervalStatsManager:
    """区间统计管理器 - 管理当前30分钟区间的实时统计"""
    
    @staticmethod
    def _get_current_interval_key() -> str:
        """获取当前30分钟区间的唯一标识"""
        now = datetime.utcnow()
        # 将时间对齐到30分钟区间
        interval_start = now.replace(minute=(now.minute // 30) * 30, second=0, microsecond=0)
        return f"{CURRENT_INTERVAL_STATS_KEY}:{interval_start.strftime('%Y%m%d_%H%M')}"
    
    @staticmethod
    async def update_current_interval() -> None:
        """更新当前区间的统计数据"""
        redis_sync = get_redis_message()
        redis_async = get_redis()
        
        try:
            # 获取当前在线和游玩用户数
            online_count = await _get_online_users_count(redis_async)
            playing_count = await _get_playing_users_count(redis_async)
            
            current_time = datetime.utcnow()
            interval_key = IntervalStatsManager._get_current_interval_key()
            
            # 准备区间统计数据
            interval_stats = {
                "timestamp": current_time.isoformat(),
                "online_count": online_count,
                "playing_count": playing_count,
                "last_updated": current_time.isoformat()
            }
            
            # 存储当前区间统计
            await _redis_exec(redis_sync.set, interval_key, json.dumps(interval_stats))
            await redis_async.expire(interval_key, 35 * 60)  # 35分钟过期，确保覆盖整个区间
            
            logger.debug(f"Updated current interval stats: online={online_count}, playing={playing_count}")
            
        except Exception as e:
            logger.error(f"Error updating current interval stats: {e}")
    
    @staticmethod
    async def get_current_interval_stats() -> Optional[Dict]:
        """获取当前区间的统计数据"""
        redis_sync = get_redis_message()
        
        try:
            interval_key = IntervalStatsManager._get_current_interval_key()
            stats_data = await _redis_exec(redis_sync.get, interval_key)
            
            if stats_data:
                return json.loads(stats_data)
            return None
            
        except Exception as e:
            logger.error(f"Error getting current interval stats: {e}")
            return None
    
    @staticmethod
    async def finalize_current_interval() -> bool:
        """完成当前区间统计，将其添加到历史记录中"""
        redis_sync = get_redis_message()
        redis_async = get_redis()
        
        try:
            # 获取当前区间的统计
            current_stats = await IntervalStatsManager.get_current_interval_stats()
            if not current_stats:
                # 如果没有当前区间数据，使用实时数据
                online_count = await _get_online_users_count(redis_async)
                playing_count = await _get_playing_users_count(redis_async)
                current_time = datetime.utcnow()
                
                current_stats = {
                    "timestamp": current_time.isoformat(),
                    "online_count": online_count,
                    "playing_count": playing_count
                }
            
            # 调整时间戳到区间结束时间
            now = datetime.utcnow()
            interval_end = now.replace(minute=(now.minute // 30) * 30, second=0, microsecond=0)
            if now.minute % 30 != 0 or now.second != 0:
                interval_end += timedelta(minutes=30)
            
            history_point = {
                "timestamp": interval_end.isoformat(),
                "online_count": current_stats["online_count"],
                "playing_count": current_stats["playing_count"]
            }
            
            # 添加到历史记录
            await _redis_exec(redis_sync.lpush, REDIS_ONLINE_HISTORY_KEY, json.dumps(history_point))
            # 只保留48个数据点（24小时，每30分钟一个点）
            await _redis_exec(redis_sync.ltrim, REDIS_ONLINE_HISTORY_KEY, 0, 47)
            # 设置过期时间为26小时，确保有足够缓冲
            await redis_async.expire(REDIS_ONLINE_HISTORY_KEY, 26 * 3600)
            
            logger.info(f"Finalized interval stats: online={current_stats['online_count']}, playing={current_stats['playing_count']} at {interval_end.strftime('%H:%M:%S')}")
            return True
            
        except Exception as e:
            logger.error(f"Error finalizing current interval: {e}")
            return False

# 便捷函数
async def update_user_activity_stats() -> None:
    """在用户活动时更新统计（登录、开始游玩等）"""
    await IntervalStatsManager.update_current_interval()

async def get_enhanced_current_stats() -> Dict:
    """获取增强的当前统计，包含区间数据"""
    from app.router.v2.stats import get_server_stats
    
    # 获取基础统计
    current_stats = await get_server_stats()
    
    # 获取区间统计
    interval_stats = await IntervalStatsManager.get_current_interval_stats()
    
    result = {
        "registered_users": current_stats.registered_users,
        "online_users": current_stats.online_users,
        "playing_users": current_stats.playing_users,
        "timestamp": current_stats.timestamp.isoformat(),
        "interval_data": interval_stats
    }
    
    return result
