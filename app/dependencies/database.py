from __future__ import annotations

from contextvars import ContextVar
import json

from app.config import settings

from pydantic import BaseModel
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession


def json_serializer(value):
    if isinstance(value, BaseModel | SQLModel):
        return value.model_dump_json()
    return json.dumps(value)


# 数据库引擎
engine = create_async_engine(
    settings.database_url,
    json_serializer=json_serializer,
    pool_size=20,
    max_overflow=20,
    pool_timeout=30.0,
)

# Redis 连接
redis_client = redis.from_url(settings.redis_url, decode_responses=True)


# 数据库依赖
db_session_context: ContextVar[AsyncSession | None] = ContextVar(
    "db_session_context", default=None
)


async def get_db():
    session = db_session_context.get()
    if session is None:
        session = AsyncSession(engine)
        db_session_context.set(session)
        try:
            yield session
        finally:
            await session.close()
            db_session_context.set(None)
    else:
        yield session


# Redis 依赖
def get_redis():
    return redis_client


def get_redis_pubsub():
    return redis_client.pubsub()
