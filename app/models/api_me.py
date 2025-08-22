"""
APIMe 响应模型 - 对应 osu! 的 APIMe 类型
"""

from __future__ import annotations

from app.database.lazer_user import UserResp


class APIMe(UserResp):
    """
    /me 端点的响应模型
    对应 osu! 的 APIMe 类型，继承 APIUser(UserResp) 并包含 session_verified 字段
    
    session_verified 字段已经在 UserResp 中定义，这里不需要重复定义
    """
    pass
