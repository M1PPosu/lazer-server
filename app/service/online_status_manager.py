"""
在线状态管理服务

此模块负责统一管理用户的在线状态，确保用户在连接WebSocket后立即显示为在线。
"""

from __future__ import annotations

from datetime import datetime

from app.dependencies.database import get_redis
from app.log import logger
from app.router.private.stats import add_online_user


class OnlineStatusManager:
    """在线状态管理器"""

    @staticmethod
    async def set_user_online(user_id: int, hub_type: str = "general") -> None:
        """
        设置用户为在线状态

        Args:
            user_id: 用户ID
            hub_type: Hub类型 (metadata, spectator, multiplayer等)
        """
        try:
            redis = get_redis()

            # 1. 添加到在线用户集合
            await add_online_user(user_id)

            # 2. 设置metadata在线标记，这是is_online检查的关键
            metadata_key = f"metadata:online:{user_id}"
            await redis.set(metadata_key, hub_type, ex=7200)  # 2小时过期

            # 3. 设置最后活跃时间戳
            last_seen_key = f"user:last_seen:{user_id}"
            await redis.set(last_seen_key, int(datetime.utcnow().timestamp()), ex=7200)

            logger.debug(f"[OnlineStatusManager] User {user_id} set online via {hub_type}")

        except Exception as e:
            logger.error(f"[OnlineStatusManager] Error setting user {user_id} online: {e}")

    @staticmethod
    async def refresh_user_online_status(user_id: int, hub_type: str = "active") -> None:
        """
        刷新用户的在线状态

        Args:
            user_id: 用户ID
            hub_type: 当前活动类型
        """
        try:
            redis = get_redis()

            # 刷新metadata在线标记
            metadata_key = f"metadata:online:{user_id}"
            await redis.set(metadata_key, hub_type, ex=7200)

            # 刷新最后活跃时间
            last_seen_key = f"user:last_seen:{user_id}"
            await redis.set(last_seen_key, int(datetime.utcnow().timestamp()), ex=7200)

            logger.debug(f"[OnlineStatusManager] Refreshed online status for user {user_id}")

        except Exception as e:
            logger.error(f"[OnlineStatusManager] Error refreshing user {user_id} status: {e}")

    @staticmethod
    async def set_user_offline(user_id: int) -> None:
        """
        设置用户为离线状态

        Args:
            user_id: 用户ID
        """
        try:
            redis = get_redis()

            # 删除metadata在线标记
            metadata_key = f"metadata:online:{user_id}"
            await redis.delete(metadata_key)

            # 从在线用户集合中移除
            from app.router.private.stats import remove_online_user

            await remove_online_user(user_id)

            logger.debug(f"[OnlineStatusManager] User {user_id} set offline")

        except Exception as e:
            logger.error(f"[OnlineStatusManager] Error setting user {user_id} offline: {e}")

    @staticmethod
    async def is_user_online(user_id: int) -> bool:
        """
        检查用户是否在线

        Args:
            user_id: 用户ID

        Returns:
            bool: 用户是否在线
        """
        try:
            redis = get_redis()
            metadata_key = f"metadata:online:{user_id}"
            is_online = await redis.exists(metadata_key)
            return bool(is_online)
        except Exception as e:
            logger.error(f"[OnlineStatusManager] Error checking user {user_id} online status: {e}")
            return False

    @staticmethod
    async def get_online_users_count() -> int:
        """
        获取在线用户数量

        Returns:
            int: 在线用户数量
        """
        try:
            from app.dependencies.database import get_redis
            from app.router.private.stats import _get_online_users_count

            redis = get_redis()
            return await _get_online_users_count(redis)
        except Exception as e:
            logger.error(f"[OnlineStatusManager] Error getting online users count: {e}")
            return 0


# 单例实例
online_status_manager = OnlineStatusManager()
