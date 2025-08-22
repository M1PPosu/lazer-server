from __future__ import annotations

from datetime import datetime, timedelta

from app.dependencies.database import get_redis, get_redis_message
from app.log import logger
from app.router.v2.stats import (
    REDIS_ONLINE_USERS_KEY,
    REDIS_PLAYING_USERS_KEY,
    _redis_exec,
)


async def cleanup_stale_online_users() -> tuple[int, int, int]:
    """清理过期的在线和游玩用户，返回清理的用户数(online_cleaned, playing_cleaned, metadata_cleaned)"""
    redis_sync = get_redis_message()
    redis_async = get_redis()

    online_cleaned = 0
    playing_cleaned = 0
    metadata_cleaned = 0

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

        # 对于游玩用户，我们使用更保守的清理策略
        # 只有当用户明确不在任何hub连接中时才移除
        stale_playing_users = []
        for user_id in playing_users:
            user_id_str = (
                user_id.decode() if isinstance(user_id, bytes) else str(user_id)
            )
            metadata_key = f"metadata:online:{user_id_str}"
            
            # 只有当metadata在线标记完全不存在且用户也不在在线列表中时，
            # 才认为用户真正离线
            if (not await redis_async.exists(metadata_key) and 
                user_id_str not in [u.decode() if isinstance(u, bytes) else str(u) for u in online_users]):
                stale_playing_users.append(user_id_str)

        # 清理过期的游玩用户
        if stale_playing_users:
            await _redis_exec(
                redis_sync.srem, REDIS_PLAYING_USERS_KEY, *stale_playing_users
            )
            playing_cleaned = len(stale_playing_users)
            logger.info(f"Cleaned {playing_cleaned} stale playing users")

        # 新增：清理过期的metadata在线标记
        # 这个步骤用于清理那些由于异常断开连接而没有被正常清理的metadata键
        metadata_cleaned = 0
        try:
            # 查找所有metadata:online:*键
            metadata_keys = []
            cursor = 0
            pattern = "metadata:online:*"
            
            # 使用SCAN命令遍历所有匹配的键
            while True:
                cursor, keys = await redis_async.scan(cursor=cursor, match=pattern, count=100)
                metadata_keys.extend(keys)
                if cursor == 0:
                    break
            
            # 检查这些键是否对应有效的在线用户
            orphaned_metadata_keys = []
            for key in metadata_keys:
                if isinstance(key, bytes):
                    key_str = key.decode()
                else:
                    key_str = key
                    
                # 从键名中提取用户ID
                user_id = key_str.replace("metadata:online:", "")
                
                # 检查用户是否在在线用户集合中
                is_in_online_set = await _redis_exec(redis_sync.sismember, REDIS_ONLINE_USERS_KEY, user_id)
                is_in_playing_set = await _redis_exec(redis_sync.sismember, REDIS_PLAYING_USERS_KEY, user_id)
                
                # 如果用户既不在在线集合也不在游玩集合中，检查TTL
                if not is_in_online_set and not is_in_playing_set:
                    # 检查键的TTL
                    ttl = await redis_async.ttl(key_str)
                    # TTL < 0 表示键没有过期时间或已过期
                    # 我们只清理那些明确过期或没有设置TTL的键
                    if ttl < 0:
                        # 再次确认键确实存在且没有对应的活跃连接
                        key_value = await redis_async.get(key_str)
                        if key_value:
                            # 键存在但用户不在任何集合中，且没有有效TTL，可以安全删除
                            orphaned_metadata_keys.append(key_str)
            
            # 清理孤立的metadata键
            if orphaned_metadata_keys:
                await redis_async.delete(*orphaned_metadata_keys)
                metadata_cleaned = len(orphaned_metadata_keys)
                logger.info(f"Cleaned {metadata_cleaned} orphaned metadata:online keys")
                
        except Exception as e:
            logger.error(f"Error cleaning orphaned metadata keys: {e}")

    except Exception as e:
        logger.error(f"Error cleaning stale users: {e}")

    return online_cleaned, playing_cleaned, metadata_cleaned


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
