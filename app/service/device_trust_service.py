"""
设备信任服务
管理用户的受信任设备，减少频繁验证
"""

from __future__ import annotations

from datetime import timedelta

from app.config import settings
from app.log import logger
from app.service.client_detection_service import ClientInfo
from app.utils import utcnow

from redis.asyncio import Redis


class DeviceTrustService:
    """设备信任服务"""

    @staticmethod
    def _get_device_trust_key(user_id: int, device_fingerprint: str) -> str:
        """获取设备信任的 Redis 键"""
        return f"device_trust:{user_id}:{device_fingerprint}"

    @staticmethod
    def _get_location_trust_key(user_id: int, country_code: str) -> str:
        """获取位置信任的 Redis 键"""
        return f"location_trust:{user_id}:{country_code}"

    @staticmethod
    def _get_verification_cooldown_key(user_id: int) -> str:
        """获取验证冷却的 Redis 键"""
        return f"verification_cooldown:{user_id}"

    @staticmethod
    async def is_device_trusted(
        redis: Redis,
        user_id: int,
        device_fingerprint: str,
    ) -> bool:
        """
        检查设备是否受信任

        Args:
            redis: Redis 连接
            user_id: 用户 ID
            device_fingerprint: 设备指纹

        Returns:
            bool: 设备是否受信任
        """
        if not device_fingerprint:
            return False

        trust_key = DeviceTrustService._get_device_trust_key(user_id, device_fingerprint)
        trust_data = await redis.get(trust_key)

        return trust_data is not None

    @staticmethod
    async def is_location_trusted(
        redis: Redis,
        user_id: int,
        country_code: str | None,
    ) -> bool:
        """
        检查位置是否受信任

        Args:
            redis: Redis 连接
            user_id: 用户 ID
            country_code: 国家代码

        Returns:
            bool: 位置是否受信任
        """
        if not country_code:
            return False

        trust_key = DeviceTrustService._get_location_trust_key(user_id, country_code)
        trust_data = await redis.get(trust_key)

        return trust_data is not None

    @staticmethod
    async def is_in_verification_cooldown(
        redis: Redis,
        user_id: int,
    ) -> bool:
        """
        检查用户是否在验证冷却期内

        Args:
            redis: Redis 连接
            user_id: 用户 ID

        Returns:
            bool: 是否在冷却期内
        """
        cooldown_key = DeviceTrustService._get_verification_cooldown_key(user_id)
        cooldown_data = await redis.get(cooldown_key)

        return cooldown_data is not None

    @staticmethod
    async def trust_device(
        redis: Redis,
        user_id: int,
        device_fingerprint: str,
        client_info: ClientInfo,
        trust_duration_days: int | None = None,
    ) -> None:
        """
        信任设备

        Args:
            redis: Redis 连接
            user_id: 用户 ID
            device_fingerprint: 设备指纹
            client_info: 客户端信息
            trust_duration_days: 信任持续天数
        """
        if not device_fingerprint:
            return

        # 使用配置中的默认值
        if trust_duration_days is None:
            trust_duration_days = settings.device_trust_duration_days

        trust_key = DeviceTrustService._get_device_trust_key(user_id, device_fingerprint)
        trust_data = {
            "client_type": client_info.client_type,
            "platform": client_info.platform or "unknown",
            "trusted_at": utcnow().isoformat(),
        }

        # 设置信任期限
        trust_duration_seconds = trust_duration_days * 24 * 3600
        await redis.setex(trust_key, trust_duration_seconds, str(trust_data))

        logger.info(
            f"[Device Trust] Device trusted for user {user_id}: "
            f"{client_info.client_type} on {client_info.platform} "
            f"(fingerprint: {device_fingerprint[:8]}...)"
        )

    @staticmethod
    async def trust_location(
        redis: Redis,
        user_id: int,
        country_code: str,
        trust_duration_days: int | None = None,
    ) -> None:
        """
        信任位置

        Args:
            redis: Redis 连接
            user_id: 用户 ID
            country_code: 国家代码
            trust_duration_days: 信任持续天数
        """
        if not country_code:
            return

        # 使用配置中的默认值
        if trust_duration_days is None:
            trust_duration_days = settings.location_trust_duration_days

        trust_key = DeviceTrustService._get_location_trust_key(user_id, country_code)
        trust_data = {
            "country_code": country_code,
            "trusted_at": utcnow().isoformat(),
        }

        # 设置信任期限
        trust_duration_seconds = trust_duration_days * 24 * 3600
        await redis.setex(trust_key, trust_duration_seconds, str(trust_data))

        logger.info(f"[Location Trust] Location trusted for user {user_id}: {country_code}")

    @staticmethod
    async def set_verification_cooldown(
        redis: Redis,
        user_id: int,
        cooldown_seconds: int,
    ) -> None:
        """
        设置验证冷却期

        Args:
            redis: Redis 连接
            user_id: 用户 ID
            cooldown_seconds: 冷却时间（秒）
        """
        cooldown_key = DeviceTrustService._get_verification_cooldown_key(user_id)
        cooldown_data = {
            "set_at": utcnow().isoformat(),
            "expires_at": (utcnow() + timedelta(seconds=cooldown_seconds)).isoformat(),
        }

        await redis.setex(cooldown_key, cooldown_seconds, str(cooldown_data))

        logger.info(f"[Verification Cooldown] Set cooldown for user {user_id}: {cooldown_seconds}s")

    @staticmethod
    async def should_require_verification(
        redis: Redis,
        user_id: int,
        device_fingerprint: str | None,
        country_code: str | None,
        client_info: ClientInfo,
        is_new_location: bool,
    ) -> tuple[bool, str]:
        """
        判断是否需要验证

        Args:
            redis: Redis 连接
            user_id: 用户 ID
            device_fingerprint: 设备指纹
            country_code: 国家代码
            client_info: 客户端信息
            is_new_location: 是否为新位置

        Returns:
            tuple[bool, str]: (是否需要验证, 原因)
        """
        # 检查验证冷却期
        if await DeviceTrustService.is_in_verification_cooldown(redis, user_id):
            return False, "用户在验证冷却期内"

        # 检查设备信任
        if device_fingerprint and await DeviceTrustService.is_device_trusted(redis, user_id, device_fingerprint):
            return False, "设备已受信任"

        # 检查位置信任
        if country_code and await DeviceTrustService.is_location_trusted(redis, user_id, country_code):
            return False, "位置已受信任"

        # 受信任的客户端类型降低验证要求
        if client_info.is_trusted_client and not is_new_location:
            return False, "受信任客户端且非新位置"

        # 如果是新位置登录，需要验证
        if is_new_location:
            return True, "新位置登录需要验证"

        # 默认不需要验证
        return False, "常规登录无需验证"

    @staticmethod
    async def mark_verification_successful(
        redis: Redis,
        user_id: int,
        device_fingerprint: str | None,
        country_code: str | None,
        client_info: ClientInfo,
    ) -> None:
        """
        标记验证成功，更新信任信息

        Args:
            redis: Redis 连接
            user_id: 用户 ID
            device_fingerprint: 设备指纹
            country_code: 国家代码
            client_info: 客户端信息
        """
        # 信任设备
        if device_fingerprint:
            await DeviceTrustService.trust_device(redis, user_id, device_fingerprint, client_info)

        # 信任位置
        if country_code:
            await DeviceTrustService.trust_location(redis, user_id, country_code)

        # 设置验证冷却期
        cooldown_seconds = (client_info.is_trusted_client and 3600) or 1800  # 受信任客户端1小时，其他30分钟
        await DeviceTrustService.set_verification_cooldown(redis, user_id, cooldown_seconds)

        logger.info(f"[Device Trust] Verification successful for user {user_id}, trust updated")
