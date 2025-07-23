from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

try:
    import redis
except ImportError:
    redis = None
from app.config import settings

# 数据库引擎
engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Redis 连接
if redis:
    redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
else:
    redis_client = None


# 数据库依赖
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Redis 依赖
def get_redis():
    return redis_client
