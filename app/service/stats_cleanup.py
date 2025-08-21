from __future__ import annotations

from datetime import datetime, timedelta

from app.dependencies.database import get_redis, get_redis_message
from app.log import logger
from app.router.v2.stats import (
    REDIS_ONLINE_USERS_KEY,
    REDIS_PLAYING_USERS_KEY,
    _redis_exec,
)


async def cleanup_stale_online_users() -> tuple[int, int]:
    """清理过期的在线和游玩用户，返回清理的用户数"""
    redis_sync = get_redis_message()
    redis_async = get_redis()

    online_cleaned = 0
    playing_cleaned = 0

    try:
        # 获取所有在线用户
        online_users = await _redis_exec(redis_sync.smembers, REDIS_ONLINE_USERS_KEY)
        playing_users = await _redis_exec(redis_sync.smembers, REDIS_PLAYING_USERS_KEY)

        # 检查在线用户的最后活动时间
        current_time = datetime.utcnow()
        stale_threshold = current_time - timedelta(hours=2)  # 2小时无活动视为过期

        # 对于在线用户，我们检查metadata在线标记
        stale_online_users = []
        for user_id in online_users:
            user_id_str = (
                user_id.decode() if isinstance(user_id, bytes) else str(user_id)
            )
            metadata_key = f"metadata:online:{user_id_str}"

            # 如果metadata标记不存在，说明用户已经离线
            if not await redis_async.exists(metadata_key):
                stale_online_users.append(user_id_str)

        # 清理过期的在线用户
        if stale_online_users:
            await _redis_exec(
                redis_sync.srem, REDIS_ONLINE_USERS_KEY, *stale_online_users
            )
            online_cleaned = len(stale_online_users)
            logger.info(f"Cleaned {online_cleaned} stale online users")

        # 对于游玩用户，我们也检查对应的spectator状态
        stale_playing_users = []
        for user_id in playing_users:
            user_id_str = (
                user_id.decode() if isinstance(user_id, bytes) else str(user_id)
            )

            # 如果用户不在在线用户列表中，说明已经离线，也应该从游玩列表中移除
            if user_id_str in stale_online_users or user_id_str not in [
                u.decode() if isinstance(u, bytes) else str(u) for u in online_users
            ]:
                stale_playing_users.append(user_id_str)

        # 清理过期的游玩用户
        if stale_playing_users:
            await _redis_exec(
                redis_sync.srem, REDIS_PLAYING_USERS_KEY, *stale_playing_users
            )
            playing_cleaned = len(stale_playing_users)
            logger.info(f"Cleaned {playing_cleaned} stale playing users")

    except Exception as e:
        logger.error(f"Error cleaning stale users: {e}")

    return online_cleaned, playing_cleaned


async def refresh_redis_key_expiry() -> None:
    """刷新Redis键的过期时间，防止数据丢失"""
    redis_async = get_redis()

    try:
        # 刷新在线用户key的过期时间
        if await redis_async.exists(REDIS_ONLINE_USERS_KEY):
            await redis_async.expire(REDIS_ONLINE_USERS_KEY, 6 * 3600)  # 6小时

        # 刷新游玩用户key的过期时间
        if await redis_async.exists(REDIS_PLAYING_USERS_KEY):
            await redis_async.expire(REDIS_PLAYING_USERS_KEY, 6 * 3600)  # 6小时

        logger.debug("Refreshed Redis key expiry times")

    except Exception as e:
        logger.error(f"Error refreshing Redis key expiry: {e}")
