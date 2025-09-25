"""
会话验证路由 - 实现类似 osu! 的邮件验证流程 (API v2)
"""

from __future__ import annotations

from typing import Annotated, Literal

from app.auth import check_totp_backup_code, verify_totp_key_with_replay_protection
from app.config import settings
from app.const import BACKUP_CODE_LENGTH
from app.database.auth import TotpKeys
from app.dependencies.api_version import APIVersion
from app.dependencies.database import Database, get_redis
from app.dependencies.geoip import get_client_ip
from app.dependencies.user import UserAndToken, get_client_user_and_token
from app.log import logger
from app.service.login_log_service import LoginLogService
from app.service.verification_service import (
    EmailVerificationService,
    LoginSessionService,
)

from .router import router

from fastapi import Depends, Form, HTTPException, Request, Security, status
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from redis.asyncio import Redis


class VerifyMethod(BaseModel):
    method: Literal["totp", "mail"] = "mail"


class SessionReissueResponse(BaseModel):
    """重新发送验证码响应"""

    success: bool
    message: str


class VerifyFailed(Exception):
    def __init__(self, message: str, reason: str | None = None, should_reissue: bool = False):
        super().__init__(message)
        self.reason = reason
        self.should_reissue = should_reissue


@router.post(
    "/session/verify",
    name="验证会话",
    description="验证邮件验证码并完成会话认证",
    status_code=204,
    tags=["验证"],
    responses={
        401: {"model": VerifyMethod, "description": "验证失败，返回当前使用的验证方法"},
        204: {"description": "验证成功，无内容返回"},
    },
)
async def verify_session(
    request: Request,
    db: Database,
    api_version: APIVersion,
    redis: Annotated[Redis, Depends(get_redis)],
    verification_key: str = Form(..., description="8 位邮件验证码或者 6 位 TOTP 代码或 10 位备份码 （g0v0 扩展支持）"),
    user_and_token: UserAndToken = Security(get_client_user_and_token),
) -> Response:
    current_user = user_and_token[0]
    token_id = user_and_token[1].id
    user_id = current_user.id

    if not await LoginSessionService.check_is_need_verification(db, user_id, token_id):
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    verify_method: str | None = (
        "mail" if api_version < 20250913 else await LoginSessionService.get_login_method(user_id, token_id, redis)
    )

    ip_address = get_client_ip(request)
    user_agent = request.headers.get("User-Agent", "Unknown")
    login_method = "password"

    try:
        totp_key: TotpKeys | None = await current_user.awaitable_attrs.totp_key
        if verify_method is None:
            # 智能选择验证方法（参考osu-web实现）
            # API版本较老或用户未设置TOTP时强制使用邮件验证
            #print(api_version, totp_key)
            if api_version < 20240101 or totp_key is None:
                verify_method = "mail"
            else:
                verify_method = "totp"
            await LoginSessionService.set_login_method(user_id, token_id, verify_method, redis)
        login_method = verify_method

        if verify_method == "totp":
            if not totp_key:
                # TOTP密钥在验证开始和现在之间被删除（参考osu-web的fallback机制）
                if settings.enable_email_verification:
                    await LoginSessionService.set_login_method(user_id, token_id, "mail", redis)
                    await EmailVerificationService.send_verification_email(
                        db, redis, user_id, current_user.username, current_user.email, ip_address, user_agent
                    )
                    verify_method = "mail"
                    raise VerifyFailed("用户TOTP已被删除，已切换到邮件验证")
                # 如果未开启邮箱验证，则直接认为认证通过
                # 正常不会进入到这里

            elif await verify_totp_key_with_replay_protection(user_id, totp_key.secret, verification_key, redis):
                pass
            elif len(verification_key) == BACKUP_CODE_LENGTH and check_totp_backup_code(totp_key, verification_key):
                login_method = "totp_backup_code"
            else:
                # 记录详细的验证失败原因（参考osu-web的错误处理）
                if len(verification_key) != 6:
                    raise VerifyFailed("TOTP验证码长度错误，应为6位数字", reason="incorrect_length")
                elif not verification_key.isdigit():
                    raise VerifyFailed("TOTP验证码格式错误，应为纯数字", reason="incorrect_format")
                else:
                    # 可能是密钥错误或者重放攻击
                    raise VerifyFailed("TOTP 验证失败，请检查验证码是否正确且未过期", reason="incorrect_key")
        else:
            success, message = await EmailVerificationService.verify_email_code(db, redis, user_id, verification_key)
            if not success:
                raise VerifyFailed(f"邮件验证失败: {message}")

        await LoginLogService.record_login(
            db=db,
            user_id=user_id,
            request=request,
            login_method=login_method,
            login_success=True,
            notes=f"{login_method} 验证成功",
        )
        await LoginSessionService.mark_session_verified(db, redis, user_id, token_id)
        await db.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except VerifyFailed as e:
        await LoginLogService.record_failed_login(
            db=db,
            request=request,
            attempted_username=current_user.username,
            login_method=login_method,
            notes=str(e),
        )

        # 构建更详细的错误响应（参考osu-web的错误处理）
        error_response = {
            "error": str(e),
            "method": verify_method,
        }

        # 如果有具体的错误原因，添加到响应中
        if hasattr(e, 'reason') and e.reason:
            error_response["reason"] = e.reason

        # 如果需要重新发送邮件验证码
        if hasattr(e, 'should_reissue') and e.should_reissue and verify_method == "mail":
            try:
                await EmailVerificationService.send_verification_email(
                    db, redis, user_id, current_user.username, current_user.email, ip_address, user_agent
                )
                error_response["reissued"] = True
            except Exception:
                pass  # 忽略重发邮件失败的错误

        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content=error_response)


@router.post(
    "/session/verify/reissue",
    name="重新发送验证码",
    description="重新发送邮件验证码",
    response_model=SessionReissueResponse,
    tags=["验证"],
)
async def reissue_verification_code(
    request: Request,
    db: Database,
    api_version: APIVersion,
    redis: Annotated[Redis, Depends(get_redis)],
    user_and_token: UserAndToken = Security(get_client_user_and_token),
) -> SessionReissueResponse:
    current_user = user_and_token[0]
    token_id = user_and_token[1].id
    user_id = current_user.id

    if not await LoginSessionService.check_is_need_verification(db, user_id, token_id):
        return SessionReissueResponse(success=False, message="当前会话不需要验证")

    verify_method: str | None = (
        "mail" if api_version < 20250913 else await LoginSessionService.get_login_method(user_id, token_id, redis)
    )
    if verify_method != "mail":
        return SessionReissueResponse(success=False, message="当前会话不支持重新发送验证码")

    try:
        ip_address = get_client_ip(request)
        user_agent = request.headers.get("User-Agent", "Unknown")
        user_id = current_user.id
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
    "/session/verify/mail-fallback",
    name="邮件验证码回退",
    description="当 TOTP 验证不可用时，使用邮件验证码进行回退验证",
    response_model=VerifyMethod,
    tags=["验证"],
)
async def fallback_email(
    db: Database,
    request: Request,
    redis: Annotated[Redis, Depends(get_redis)],
    user_and_token: UserAndToken = Security(get_client_user_and_token),
) -> VerifyMethod:
    current_user = user_and_token[0]
    token_id = user_and_token[1].id
    if not await LoginSessionService.get_login_method(current_user.id, token_id, redis):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前会话不需要回退")

    ip_address = get_client_ip(request)
    user_agent = request.headers.get("User-Agent", "Unknown")

    await LoginSessionService.set_login_method(current_user.id, token_id, "mail", redis)
    success, message = await EmailVerificationService.resend_verification_code(
        db,
        redis,
        current_user.id,
        current_user.username,
        current_user.email,
        ip_address,
        user_agent,
    )
    if not success:
        logger.error(
            f"[Email Fallback] Failed to send fallback email to user {current_user.id} (token: {token_id}): {message}"
        )
    return VerifyMethod()
