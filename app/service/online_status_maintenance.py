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
    但不会恢复已经退出的用户的在线状态。
    """
    redis_sync = get_redis_message()
    redis_async = get_redis()
    
    try:
        # 获取所有正在游玩的用户
        playing_users = await _redis_exec(redis_sync.smembers, REDIS_PLAYING_USERS_KEY)
        
        if not playing_users:
            return
            
        logger.debug(f"Checking online status for {len(playing_users)} playing users")
        
        # 仅为当前有效连接的用户刷新在线状态
        updated_count = 0
        for user_id in playing_users:
            user_id_str = user_id.decode() if isinstance(user_id, bytes) else str(user_id)
            metadata_key = f"metadata:online:{user_id_str}"
            
            # 重要：首先检查用户是否已经有在线标记，只有存在才刷新
            if await redis_async.exists(metadata_key):
                # 只更新已经在线的用户的状态，不恢复已退出的用户
                await redis_async.set(metadata_key, "playing", ex=3600)
                updated_count += 1
            else:
                # 如果用户已退出（没有在线标记），则从游玩用户中移除
                await _redis_exec(redis_sync.srem, REDIS_PLAYING_USERS_KEY, user_id)
                logger.debug(f"Removed user {user_id_str} from playing users as they are offline")
            
        logger.debug(f"Updated metadata online status for {updated_count} playing users")
        
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
