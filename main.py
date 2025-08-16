from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
import os

from app.config import settings
from app.dependencies.database import engine, redis_client
from app.dependencies.fetcher import get_fetcher
from app.dependencies.scheduler import init_scheduler, stop_scheduler
from app.log import logger
from app.router import (
    api_v1_router,
    api_v2_router,
    auth_router,
    chat_router,
    fetcher_router,
    file_router,
    private_router,
    redirect_api_router,
    signalr_router,
)
from app.router.redirect import redirect_router
from app.service.calculate_all_user_rank import calculate_user_rank
from app.service.create_banchobot import create_banchobot
from app.service.daily_challenge import daily_challenge_job
from app.service.osu_rx_statistics import create_rx_statistics
from app.service.pp_recalculate import recalculate_all_players_pp

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import sentry_sdk


@asynccontextmanager
async def lifespan(app: FastAPI):
    # on startup
    await get_fetcher()  # 初始化 fetcher
    if os.environ.get("RECALCULATE_PP", "false").lower() == "true":
        await recalculate_all_players_pp()
    await create_rx_statistics()
    await calculate_user_rank(True)
    init_scheduler()
    await daily_challenge_job()
    await create_banchobot()
    # on shutdown
    yield
    stop_scheduler()
    await engine.dispose()
    await redis_client.aclose()


desc = (
    "osu! API 模拟服务器，支持 osu! API v1, v2 和 osu!lazer 的绝大部分功能。\n\n"
    "官方文档：[osu!web 文档](https://osu.ppy.sh/docs/index.html)\n\n"
    "V1 API 文档：[osu-api](https://github.com/ppy/osu-api/wiki)"
)

if settings.sentry_dsn is not None:
    sentry_sdk.init(
        dsn=str(settings.sentry_dsn),
        send_default_pii=False,
        environment="production" if not settings.debug else "development",
    )

app = FastAPI(
    title="osu! API 模拟服务器",
    version="1.0.0",
    lifespan=lifespan,
    description=desc,
)

app.include_router(api_v2_router)
app.include_router(api_v1_router)
app.include_router(chat_router)
app.include_router(redirect_api_router)
app.include_router(signalr_router)
app.include_router(fetcher_router)
app.include_router(file_router)
app.include_router(auth_router)
app.include_router(private_router)
# CORS 配置
origins = []
for url in [*settings.cors_urls, settings.server_url]:
    origins.append(str(url))
    origins.append(str(url).removesuffix("/"))
if settings.frontend_url:
    origins.append(str(settings.frontend_url))
    origins.append(str(settings.frontend_url).removesuffix("/"))
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if settings.frontend_url is not None:
    app.include_router(redirect_router)


@app.get("/", include_in_schema=False)
async def root():
    """根端点"""
    return {"message": "osu! API 模拟服务器正在运行"}


@app.get("/health", include_in_schema=False)
async def health_check():
    """健康检查端点"""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "error": exc.errors(),
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(requst: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


if settings.secret_key == "your_jwt_secret_here":
    logger.warning(
        "jwt_secret_key is unset. Your server is unsafe. "
        "Use this command to generate: openssl rand -hex 32"
    )
if settings.osu_web_client_secret == "your_osu_web_client_secret_here":
    logger.warning(
        "osu_web_client_secret is unset. Your server is unsafe. "
        "Use this command to generate: openssl rand -hex 40"
    )

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_config=None,  # 禁用uvicorn默认日志配置
        access_log=True,  # 启用访问日志
    )
