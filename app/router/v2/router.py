from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/v2")

# 导入所有子路由模块来注册路由
from . import stats  # 统计路由
