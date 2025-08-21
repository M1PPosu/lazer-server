from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import json
from typing import Any
from concurrent.futures import ThreadPoolExecutor

from app.dependencies.database import get_redis, get_redis_message
from app.log import logger

from .router import router

from fastapi import APIRouter
from pydantic import BaseModel

# Redis key constants
REDIS_ONLINE_USERS_KEY = "server:online_users"
REDIS_PLAYING_USERS_KEY = "server:playing_users"  
REDIS_REGISTERED_USERS_KEY = "server:registered_users"
REDIS_ONLINE_HISTORY_KEY = "server:online_history"

# 线程池用于同步Redis操作
_executor = ThreadPoolExecutor(max_workers=2)

async def _redis_exec(func, *args, **kwargs):
    """在线程池中执行同步Redis操作"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, func, *args, **kwargs)

class ServerStats(BaseModel):
    """服务器统计信息响应模型"""
    registered_users: int
    online_users: int
    playing_users: int
    timestamp: datetime

class OnlineHistoryPoint(BaseModel):
    """在线历史数据点"""
    timestamp: datetime
    online_count: int
    playing_count: int

class OnlineHistoryResponse(BaseModel):
    """24小时在线历史响应模型"""
    history: list[OnlineHistoryPoint]
    current_stats: ServerStats

@router.get("/stats", response_model=ServerStats, tags=["统计"])
async def get_server_stats() -> ServerStats:
    """
    获取服务器实时统计信息
    
    返回服务器注册用户数、在线用户数、正在游玩用户数等实时统计信息
    """
    redis = get_redis()
    
    try:
        # 并行获取所有统计数据
        registered_count, online_count, playing_count = await asyncio.gather(
            _get_registered_users_count(redis),
            _get_online_users_count(redis),
            _get_playing_users_count(redis)
        )
        
        return ServerStats(
            registered_users=registered_count,
            online_users=online_count,
            playing_users=playing_count,
            timestamp=datetime.utcnow()
        )
    except Exception as e:
        logger.error(f"Error getting server stats: {e}")
        # 返回默认值
        return ServerStats(
            registered_users=0,
            online_users=0,
            playing_users=0,
            timestamp=datetime.utcnow()
        )

@router.get("/stats/history", response_model=OnlineHistoryResponse, tags=["统计"])
async def get_online_history() -> OnlineHistoryResponse:
    """
    获取最近24小时在线统计历史
    
    返回过去24小时内每小时的在线用户数和游玩用户数统计，
    包含当前实时数据作为最新数据点
    """
    try:
        # 获取历史数据 - 使用同步Redis客户端
        redis_sync = get_redis_message()
        history_data = await _redis_exec(redis_sync.lrange, REDIS_ONLINE_HISTORY_KEY, 0, -1)
        history_points = []
        
        # 处理历史数据
        for data in history_data:
            try:
                point_data = json.loads(data)
                # 只保留基本字段
                history_points.append(OnlineHistoryPoint(
                    timestamp=datetime.fromisoformat(point_data["timestamp"]),
                    online_count=point_data["online_count"],
                    playing_count=point_data["playing_count"]
                ))
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                logger.warning(f"Invalid history data point: {data}, error: {e}")
                continue
        
        # 获取当前实时统计信息
        current_stats = await get_server_stats()
        
        # 如果历史数据为空或者最新数据超过15分钟，添加当前数据点
        if not history_points or (
            history_points and 
            (current_stats.timestamp - max(history_points, key=lambda x: x.timestamp).timestamp).total_seconds() > 15 * 60
        ):
            history_points.append(OnlineHistoryPoint(
                timestamp=current_stats.timestamp,
                online_count=current_stats.online_users,
                playing_count=current_stats.playing_users
            ))
        
        # 按时间排序（最新的在前）
        history_points.sort(key=lambda x: x.timestamp, reverse=True)
        
        # 限制到最多48个数据点（24小时）
        history_points = history_points[:48]
        
        return OnlineHistoryResponse(
            history=history_points,
            current_stats=current_stats
        )
    except Exception as e:
        logger.error(f"Error getting online history: {e}")
        # 返回空历史和当前状态
        current_stats = await get_server_stats()
        return OnlineHistoryResponse(
            history=[],
            current_stats=current_stats
        )

@router.get("/stats/debug", tags=["统计"])
async def get_stats_debug_info():
    """
    获取统计系统调试信息
    
    用于调试时间对齐和区间统计问题
    """
    try:
        from app.service.enhanced_interval_stats import EnhancedIntervalStatsManager
        
        current_time = datetime.utcnow()
        current_interval = await EnhancedIntervalStatsManager.get_current_interval_info()
        interval_stats = await EnhancedIntervalStatsManager.get_current_interval_stats()
        
        # 获取Redis中的实际数据
        redis_sync = get_redis_message()
        
        online_key = f"server:interval_online_users:{current_interval.interval_key}"
        playing_key = f"server:interval_playing_users:{current_interval.interval_key}"
        
        online_users_raw = await _redis_exec(redis_sync.smembers, online_key)
        playing_users_raw = await _redis_exec(redis_sync.smembers, playing_key)
        
        online_users = [int(uid.decode() if isinstance(uid, bytes) else uid) for uid in online_users_raw]
        playing_users = [int(uid.decode() if isinstance(uid, bytes) else uid) for uid in playing_users_raw]
        
        return {
            "current_time": current_time.isoformat(),
            "current_interval": {
                "start_time": current_interval.start_time.isoformat(),
                "end_time": current_interval.end_time.isoformat(),
                "key": current_interval.interval_key,
                "is_current": current_interval.is_current(),
                "minutes_remaining": int((current_interval.end_time - current_time).total_seconds() / 60),
                "seconds_remaining": int((current_interval.end_time - current_time).total_seconds()),
                "progress_percentage": round((1 - (current_interval.end_time - current_time).total_seconds() / (30 * 60)) * 100, 1)
            },
            "interval_statistics": interval_stats.to_dict() if interval_stats else None,
            "redis_data": {
                "online_users": online_users,
                "playing_users": playing_users,
                "online_count": len(online_users),
                "playing_count": len(playing_users)
            },
            "system_status": {
                "stats_system": "enhanced_interval_stats",
                "data_alignment": "30_minute_boundaries",
                "real_time_updates": True,
                "auto_24h_fill": True
            }
        }
    except Exception as e:
        logger.error(f"Error getting debug info: {e}")
        return {
            "error": "Failed to retrieve debug information",
            "message": str(e)
        }

async def _get_registered_users_count(redis) -> int:
    """获取注册用户总数（从缓存）"""
    try:
        count = await redis.get(REDIS_REGISTERED_USERS_KEY)
        return int(count) if count else 0
    except Exception as e:
        logger.error(f"Error getting registered users count: {e}")
        return 0

async def _get_online_users_count(redis) -> int:
    """获取当前在线用户数"""
    try:
        count = await redis.scard(REDIS_ONLINE_USERS_KEY)
        return count
    except Exception as e:
        logger.error(f"Error getting online users count: {e}")
        return 0

async def _get_playing_users_count(redis) -> int:
    """获取当前游玩用户数"""
    try:
        count = await redis.scard(REDIS_PLAYING_USERS_KEY)
        return count
    except Exception as e:
        logger.error(f"Error getting playing users count: {e}")
        return 0

# 统计更新功能
async def update_registered_users_count() -> None:
    """更新注册用户数缓存"""
    from app.dependencies.database import with_db
    from app.database import User
    from app.const import BANCHOBOT_ID
    from sqlmodel import select, func
    
    redis = get_redis()
    try:
        async with with_db() as db:
            # 排除机器人用户（BANCHOBOT_ID）
            result = await db.exec(
                select(func.count()).select_from(User).where(User.id != BANCHOBOT_ID)
            )
            count = result.first()
            await redis.set(REDIS_REGISTERED_USERS_KEY, count or 0, ex=300)  # 5分钟过期
            logger.debug(f"Updated registered users count: {count}")
    except Exception as e:
        logger.error(f"Error updating registered users count: {e}")

async def add_online_user(user_id: int) -> None:
    """添加在线用户"""
    redis_sync = get_redis_message()
    redis_async = get_redis()
    try:
        await _redis_exec(redis_sync.sadd, REDIS_ONLINE_USERS_KEY, str(user_id))
        # 检查key是否已有过期时间，如果没有则设置3小时过期
        ttl = await redis_async.ttl(REDIS_ONLINE_USERS_KEY)
        if ttl <= 0:  # -1表示永不过期，-2表示不存在，0表示已过期
            await redis_async.expire(REDIS_ONLINE_USERS_KEY, 3 * 3600)  # 3小时过期
        logger.debug(f"Added online user {user_id}")
        
        # 立即更新当前区间统计
        from app.service.enhanced_interval_stats import update_user_activity_in_interval
        asyncio.create_task(update_user_activity_in_interval(user_id, is_playing=False))
        
    except Exception as e:
        logger.error(f"Error adding online user {user_id}: {e}")

async def remove_online_user(user_id: int) -> None:
    """移除在线用户"""
    redis_sync = get_redis_message()
    try:
        await _redis_exec(redis_sync.srem, REDIS_ONLINE_USERS_KEY, str(user_id))
        await _redis_exec(redis_sync.srem, REDIS_PLAYING_USERS_KEY, str(user_id))
    except Exception as e:
        logger.error(f"Error removing online user {user_id}: {e}")

async def add_playing_user(user_id: int) -> None:
    """添加游玩用户"""
    redis_sync = get_redis_message()
    redis_async = get_redis()
    try:
        await _redis_exec(redis_sync.sadd, REDIS_PLAYING_USERS_KEY, str(user_id))
        # 检查key是否已有过期时间，如果没有则设置3小时过期
        ttl = await redis_async.ttl(REDIS_PLAYING_USERS_KEY)
        if ttl <= 0:  # -1表示永不过期，-2表示不存在，0表示已过期
            await redis_async.expire(REDIS_PLAYING_USERS_KEY, 3 * 3600)  # 3小时过期
        logger.debug(f"Added playing user {user_id}")
        
        # 立即更新当前区间统计
        from app.service.enhanced_interval_stats import update_user_activity_in_interval
        asyncio.create_task(update_user_activity_in_interval(user_id, is_playing=True))
        
    except Exception as e:
        logger.error(f"Error adding playing user {user_id}: {e}")

async def remove_playing_user(user_id: int) -> None:
    """移除游玩用户"""
    redis_sync = get_redis_message()
    try:
        await _redis_exec(redis_sync.srem, REDIS_PLAYING_USERS_KEY, str(user_id))
    except Exception as e:
        logger.error(f"Error removing playing user {user_id}: {e}")

async def record_hourly_stats() -> None:
    """记录统计数据 - 简化版本，主要作为fallback使用"""
    redis_sync = get_redis_message()
    redis_async = get_redis()
    try:
        # 先确保Redis连接正常
        await redis_async.ping()
        
        online_count = await _get_online_users_count(redis_async)
        playing_count = await _get_playing_users_count(redis_async)
        
        current_time = datetime.utcnow()
        history_point = {
            "timestamp": current_time.isoformat(),
            "online_count": online_count,
            "playing_count": playing_count
        }
        
        # 添加到历史记录
        await _redis_exec(redis_sync.lpush, REDIS_ONLINE_HISTORY_KEY, json.dumps(history_point))
        # 只保留48个数据点（24小时，每30分钟一个点）
        await _redis_exec(redis_sync.ltrim, REDIS_ONLINE_HISTORY_KEY, 0, 47)
        # 设置过期时间为26小时，确保有足够缓冲
        await redis_async.expire(REDIS_ONLINE_HISTORY_KEY, 26 * 3600)
        
        logger.info(f"Recorded fallback stats: online={online_count}, playing={playing_count} at {current_time.strftime('%H:%M:%S')}")
    except Exception as e:
        logger.error(f"Error recording fallback stats: {e}")
