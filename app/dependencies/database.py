from __future__ import annotations

from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

try:
    import redis
except ImportError:
    redis = None
from app.config import settings

# 数据库引擎
engine = create_async_engine(settings.DATABASE_URL)

# Redis 连接
if redis:
    redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
else:
    redis_client = None


# 数据库依赖
async def get_db():
    async with AsyncSession(engine) as session:
        yield session


async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


# Redis 依赖
def get_redis():
    return redis_client
