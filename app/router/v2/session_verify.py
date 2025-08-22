"""
会话验证路由 - 实现类似 osu! 的邮件验证流程 (API v2)
"""

from __future__ import annotations

from typing import Annotated

from app.database import User
from app.dependencies import get_current_user
from app.dependencies.database import Database, get_redis
from app.dependencies.geoip import GeoIPHelper, get_geoip_helper
from app.service.email_verification_service import (
    EmailVerificationService,
    LoginSessionService,
)
from app.service.login_log_service import LoginLogService

from .router import router

from fastapi import Depends, Form, HTTPException, Request, Security, status
from fastapi.responses import Response
from pydantic import BaseModel
from redis.asyncio import Redis


class SessionReissueResponse(BaseModel):
    """重新发送验证码响应"""

    success: bool
    message: str


@router.post(
    "/session/verify",
    name="验证会话",
    description="验证邮件验证码并完成会话认证",
    status_code=204,
)
async def verify_session(
    request: Request,
    db: Database,
    redis: Annotated[Redis, Depends(get_redis)],
    verification_key: str = Form(..., description="8位邮件验证码"),
    current_user: User = Security(get_current_user),
) -> Response:
    """
    验证邮件验证码并完成会话认证

    对应 osu! 的 session/verify 接口
    成功时返回 204 No Content，失败时返回 401 Unauthorized
    """
    try:
        from app.dependencies.geoip import get_client_ip

        ip_address = get_client_ip(request)  # noqa: F841
        user_agent = request.headers.get("User-Agent", "Unknown")  # noqa: F841

        # 从当前认证用户获取信息
        user_id = current_user.id
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户未认证")

        # 验证邮件验证码
        success, message = await EmailVerificationService.verify_code(db, redis, user_id, verification_key)

        if success:
            # 记录成功的邮件验证
            await LoginLogService.record_login(
                db=db,
                user_id=user_id,
                request=request,
                login_method="email_verification",
                login_success=True,
                notes="邮件验证成功",
            )

            # 返回 204 No Content 表示验证成功
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        else:
            # 记录失败的邮件验证尝试
            await LoginLogService.record_failed_login(
                db=db,
                request=request,
                attempted_username=current_user.username,
                login_method="email_verification",
                notes=f"邮件验证失败: {message}",
            )

            # 返回 401 Unauthorized 表示验证失败
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=message)

    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的用户会话")
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="验证过程中发生错误")


@router.post(
    "/session/verify/reissue",
    name="重新发送验证码",
    description="重新发送邮件验证码",
    response_model=SessionReissueResponse,
)
async def reissue_verification_code(
    request: Request,
    db: Database,
    redis: Annotated[Redis, Depends(get_redis)],
    current_user: User = Security(get_current_user),
) -> SessionReissueResponse:
    """
    重新发送邮件验证码

    对应 osu! 的 session/verify/reissue 接口
    """
    try:
        from app.dependencies.geoip import get_client_ip

        ip_address = get_client_ip(request)
        user_agent = request.headers.get("User-Agent", "Unknown")

        # 从当前认证用户获取信息
        user_id = current_user.id
        if not user_id:
            return SessionReissueResponse(success=False, message="用户未认证")

        # 重新发送验证码
        success, message = await EmailVerificationService.resend_verification_code(
            db,
            redis,
            user_id,
            current_user.username,
            current_user.email,
            ip_address,
            user_agent,
        )

        return SessionReissueResponse(success=success, message=message)

    except ValueError:
        return SessionReissueResponse(success=False, message="无效的用户会话")
    except Exception:
        return SessionReissueResponse(success=False, message="重新发送过程中发生错误")


@router.post(
    "/session/check-new-location",
    name="检查新位置登录",
    description="检查登录是否来自新位置（内部接口）",
)
async def check_new_location(
    request: Request,
    db: Database,
    user_id: int,
    geoip: GeoIPHelper = Depends(get_geoip_helper),
):
    """
    检查是否为新位置登录
    这是一个内部接口，用于登录流程中判断是否需要邮件验证
    """
    try:
        from app.dependencies.geoip import get_client_ip

        ip_address = get_client_ip(request)
        geo_info = geoip.lookup(ip_address)
        country_code = geo_info.get("country_iso", "XX")

        is_new_location = await LoginSessionService.check_new_location(db, user_id, ip_address, country_code)

        return {
            "is_new_location": is_new_location,
            "ip_address": ip_address,
            "country_code": country_code,
        }

    except Exception as e:
        return {
            "is_new_location": True,  # 出错时默认为新位置
            "error": str(e),
        }
