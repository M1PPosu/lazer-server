from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime

from app.config import settings
from app.dependencies.database import engine, redis_client
from app.dependencies.fetcher import get_fetcher
from app.dependencies.scheduler import init_scheduler, stop_scheduler
from app.log import logger
from app.router import (
    api_router,
    auth_router,
    fetcher_router,
    signalr_router,
)
from app.service.daily_challenge import daily_challenge_job
from app.service.osu_rx_statistics import create_rx_statistics

from fastapi import FastAPI


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


app = FastAPI(title="osu! API 模拟服务器", version="1.0.0", lifespan=lifespan)
app.include_router(api_router, prefix="/api/v2")
app.include_router(signalr_router, prefix="/signalr")
app.include_router(fetcher_router, prefix="/fetcher")
app.include_router(auth_router)


@app.get("/")
async def root():
    """根端点"""
    return {"message": "osu! API 模拟服务器正在运行"}


@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


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
