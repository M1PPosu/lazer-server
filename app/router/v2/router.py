from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/v2")

# 导入所有子路由模块来注册路由
