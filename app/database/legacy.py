# ruff: noqa: I002
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Column, DateTime
from sqlmodel import Field, Relationship, SQLModel
from sqlalchemy.orm import Mapped

if TYPE_CHECKING:
    from .user import User
# ============================================
# 旧的兼容性表模型（保留以便向后兼容）
# ============================================


class LegacyUserStatistics(SQLModel, table=True):
    __tablename__ = "user_statistics"  # pyright: ignore[reportAssignmentType]

    id: int | None = Field(default=None, primary_key=True, index=True)
    user_id: int = Field(foreign_key="users.id")
    mode: str = Field(max_length=10)  # osu, taiko, fruits, mania

    # 基本统计
    count_100: int = Field(default=0)
    count_300: int = Field(default=0)
    count_50: int = Field(default=0)
    count_miss: int = Field(default=0)

    # 等级信息
    level_current: int = Field(default=1)
    level_progress: int = Field(default=0)

    # 排名信息
    global_rank: int | None = Field(default=None)
    global_rank_exp: int | None = Field(default=None)
    country_rank: int | None = Field(default=None)

    # PP 和分数
    pp: float = Field(default=0.0)
    pp_exp: float = Field(default=0.0)
    ranked_score: int = Field(default=0)
    hit_accuracy: float = Field(default=0.0)
    total_score: int = Field(default=0)
    total_hits: int = Field(default=0)
    maximum_combo: int = Field(default=0)

    # 游戏统计
    play_count: int = Field(default=0)
    play_time: int = Field(default=0)
    replays_watched_by_others: int = Field(default=0)
    is_ranked: bool = Field(default=False)

    # 成绩等级计数
    grade_ss: int = Field(default=0)
    grade_ssh: int = Field(default=0)
    grade_s: int = Field(default=0)
    grade_sh: int = Field(default=0)
    grade_a: int = Field(default=0)

    # 最高排名记录
    rank_highest: int | None = Field(default=None)
    rank_highest_updated_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime)
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow, sa_column=Column(DateTime)
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, sa_column=Column(DateTime)
    )

    # 关联关系
    user: Mapped["User"] = Relationship(back_populates="statistics")


class LegacyOAuthToken(SQLModel, table=True):
    __tablename__ = "legacy_oauth_tokens"  # pyright: ignore[reportAssignmentType]

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    access_token: str = Field(max_length=255, index=True)
    refresh_token: str = Field(max_length=255, index=True)
    expires_at: datetime = Field(sa_column=Column(DateTime))
    created_at: datetime = Field(
        default_factory=datetime.utcnow, sa_column=Column(DateTime)
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, sa_column=Column(DateTime)
    )
    previous_usernames: list = Field(default_factory=list, sa_column=Column(JSON))
    replays_watched_counts: list = Field(default_factory=list, sa_column=Column(JSON))

    # 用户关系
    user: "User" = Relationship()
