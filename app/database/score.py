from __future__ import annotations

from datetime import datetime
from . import User
from sqlalchemy import Column, DateTime
from sqlmodel import Field, Relationship, SQLModel

class Score(SQLModel, table=True):
    """
    成绩数据库模型，对应osu! API中的Score对象
    参考: https://osu.ppy.sh/docs/index.html#score
    数据库表结构参考: migrations/base.sql
    """
    __tablename__ = "scores"

    # 基本字段
    id: int = Field(primary_key=True)
    map_md5: str = Field(max_length=32, index=True)
    score: int
    pp: float
    acc: float
    max_combo: int
    mods: int = Field(index=True)
    n300: int
    n100: int
    n50: int
    nmiss: int
    ngeki: int
    nkatu: int
    grade: str = Field(default="N", max_length=2)
    status: int = Field(index=True)
    mode: int = Field(index=True)
    play_time: datetime = Field(sa_column=Column(DateTime, index=True))
    time_elapsed: int
    client_flags: int
    userid: int = Field(index=True)
    perfect: bool
    online_checksum: str = Field(max_length=32, index=True)

    # 关联关系
    user: "User" = Relationship(back_populates="scores")
