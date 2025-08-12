from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime

from app.config import settings
from app.dependencies.database import engine, redis_client
from app.dependencies.fetcher import get_fetcher
from app.dependencies.scheduler import init_scheduler, stop_scheduler
from app.log import logger
from app.router import (
    api_v2_router,
    auth_router,
    fetcher_router,
    file_router,
    private_router,
    signalr_router,
)
from app.router.redirect import redirect_router
from app.service.daily_challenge import daily_challenge_job
from app.service.osu_rx_statistics import create_rx_statistics

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    # on startup
    await create_rx_statistics()
    await get_fetcher()  # 初始化 fetcher
    init_scheduler()
    await daily_challenge_job()
    # on shutdown
    yield
    stop_scheduler()
    await engine.dispose()
    await redis_client.aclose()


app = FastAPI(
    title="osu! API 模拟服务器",
    version="1.0.0",
    lifespan=lifespan,
    summary="osu! API 模拟服务器，支持 osu! API v2 和 osu!lazer 的绝大部分功能。官方文档：https://osu.ppy.sh/docs/index.html",
)

app.include_router(api_v2_router)
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


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if request.url.path.startswith("/api/v2"):
        return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})
    raise exc


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
if settings.private_api_secret == "your_private_api_secret_here":
    logger.warning(
        "private_api_secret is unset. Your server is unsafe. "
        "Use this command to generate: openssl rand -hex 32"
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
