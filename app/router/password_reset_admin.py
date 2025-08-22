"""
密码重置管理接口
"""

from __future__ import annotations

from app.dependencies.database import get_redis
from app.log import logger
from app.service.password_reset_service import password_reset_service

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from redis.asyncio import Redis

router = APIRouter(prefix="/admin/password-reset", tags=["密码重置管理"])


@router.get("/status/{email}", name="查询重置状态", description="查询指定邮箱的密码重置状态")
async def get_password_reset_status(
    email: str,
    redis: Redis = Depends(get_redis),
):
    """查询密码重置状态"""
    try:
        info = await password_reset_service.get_reset_code_info(email, redis)
        return JSONResponse(status_code=200, content={"success": True, "data": info})
    except Exception as e:
        logger.error(f"[Admin] Failed to get password reset status for {email}: {e}")
        return JSONResponse(status_code=500, content={"success": False, "error": "获取状态失败"})


@router.delete(
    "/cleanup/{email}",
    name="清理重置数据",
    description="强制清理指定邮箱的密码重置数据",
)
async def force_cleanup_reset(
    email: str,
    redis: Redis = Depends(get_redis),
):
    """强制清理密码重置数据"""
    try:
        success = await password_reset_service.force_cleanup_user_reset(email, redis)

        if success:
            return JSONResponse(
                status_code=200,
                content={"success": True, "message": f"已清理邮箱 {email} 的重置数据"},
            )
        else:
            return JSONResponse(status_code=500, content={"success": False, "error": "清理失败"})
    except Exception as e:
        logger.error(f"[Admin] Failed to cleanup password reset for {email}: {e}")
        return JSONResponse(status_code=500, content={"success": False, "error": "清理操作失败"})


@router.post(
    "/cleanup/expired",
    name="清理过期验证码",
    description="清理所有过期的密码重置验证码",
)
async def cleanup_expired_codes(
    redis: Redis = Depends(get_redis),
):
    """清理过期验证码"""
    try:
        count = await password_reset_service.cleanup_expired_codes(redis)
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": f"已清理 {count} 个过期的验证码",
                "cleaned_count": count,
            },
        )
    except Exception as e:
        logger.error(f"[Admin] Failed to cleanup expired codes: {e}")
        return JSONResponse(status_code=500, content={"success": False, "error": "清理操作失败"})


@router.get("/stats", name="重置统计", description="获取密码重置的统计信息")
async def get_reset_statistics(
    redis: Redis = Depends(get_redis),
):
    """获取重置统计信息"""
    try:
        # 获取所有重置相关的键
        reset_keys = await redis.keys("password_reset:code:*")
        rate_limit_keys = await redis.keys("password_reset:rate_limit:*")

        active_resets = 0
        used_resets = 0
        active_rate_limits = 0

        # 统计活跃重置
        for key in reset_keys:
            data_str = await redis.get(key)
            if data_str:
                try:
                    import json

                    data = json.loads(data_str)
                    if data.get("used", False):
                        used_resets += 1
                    else:
                        active_resets += 1
                except Exception:
                    pass

        # 统计频率限制
        for key in rate_limit_keys:
            ttl = await redis.ttl(key)
            if ttl > 0:
                active_rate_limits += 1

        stats = {
            "total_reset_codes": len(reset_keys),
            "active_resets": active_resets,
            "used_resets": used_resets,
            "active_rate_limits": active_rate_limits,
            "total_rate_limit_keys": len(rate_limit_keys),
        }

        return JSONResponse(status_code=200, content={"success": True, "data": stats})

    except Exception as e:
        logger.error(f"[Admin] Failed to get reset statistics: {e}")
        return JSONResponse(status_code=500, content={"success": False, "error": "获取统计信息失败"})
