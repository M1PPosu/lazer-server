from __future__ import annotations

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
engine = create_async_engine(settings.DATABASE_URL, json_serializer=json_serializer)

# Redis 连接
redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)


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


def get_redis_pubsub():
    return redis_client.pubsub()
