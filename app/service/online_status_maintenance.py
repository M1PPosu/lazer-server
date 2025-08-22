"""
在线状态维护服务

此模块提供在游玩状态下维护用户在线状态的功能，
解决游玩时显示离线的问题。
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from app.dependencies.database import get_redis
from app.log import logger
from app.router.v2.stats import REDIS_PLAYING_USERS_KEY, _redis_exec, get_redis_message


async def maintain_playing_users_online_status():
    """
    维护正在游玩用户的在线状态
    
    定期刷新正在游玩用户的metadata在线标记，
    确保他们在游玩过程中显示为在线状态。
    """
    redis_sync = get_redis_message()
    redis_async = get_redis()
    
    try:
        # 获取所有正在游玩的用户
        playing_users = await _redis_exec(redis_sync.smembers, REDIS_PLAYING_USERS_KEY)
        
        if not playing_users:
            return
            
        logger.debug(f"Maintaining online status for {len(playing_users)} playing users")
        
        # 为每个游玩用户刷新metadata在线标记
        for user_id in playing_users:
            user_id_str = user_id.decode() if isinstance(user_id, bytes) else str(user_id)
            metadata_key = f"metadata:online:{user_id_str}"
            
            # 设置或刷新metadata在线标记，过期时间为1小时
            await redis_async.set(metadata_key, "playing", ex=3600)
            
        logger.debug(f"Updated metadata online status for {len(playing_users)} playing users")
        
    except Exception as e:
        logger.error(f"Error maintaining playing users online status: {e}")


async def start_online_status_maintenance_task():
    """
    启动在线状态维护任务
    
    每5分钟运行一次维护任务，确保游玩用户保持在线状态
    """
    logger.info("Starting online status maintenance task")
    
    while True:
        try:
            await maintain_playing_users_online_status()
            # 每5分钟运行一次
            await asyncio.sleep(300)
        except Exception as e:
            logger.error(f"Error in online status maintenance task: {e}")
            # 出错后等待30秒再重试
            await asyncio.sleep(30)


def schedule_online_status_maintenance():
    """
    调度在线状态维护任务
    """
    task = asyncio.create_task(start_online_status_maintenance_task())
    return task
