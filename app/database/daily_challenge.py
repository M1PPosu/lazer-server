from datetime import datetime
from typing import TYPE_CHECKING

from app.models.model import UTCBaseModel

from sqlmodel import (
    BigInteger,
    Column,
    DateTime,
    Field,
    ForeignKey,
    Relationship,
    SQLModel,
)

if TYPE_CHECKING:
    from .lazer_user import User


class DailyChallengeStatsBase(SQLModel, UTCBaseModel):
    daily_streak_best: int = Field(default=0)
    daily_streak_current: int = Field(default=0)
    last_update: datetime | None = Field(default=None, sa_column=Column(DateTime))
    last_weekly_streak: datetime | None = Field(
        default=None, sa_column=Column(DateTime)
    )
    playcount: int = Field(default=0)
    top_10p_placements: int = Field(default=0)
    top_50p_placements: int = Field(default=0)
    weekly_streak_best: int = Field(default=0)
    weekly_streak_current: int = Field(default=0)


class DailyChallengeStats(DailyChallengeStatsBase, table=True):
    __tablename__ = "daily_challenge_stats"  # pyright: ignore[reportAssignmentType]

    user_id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger,
            ForeignKey("lazer_users.id"),
            unique=True,
            index=True,
            primary_key=True,
        ),
    )
    user: "User" = Relationship(back_populates="daily_challenge_stats")


class DailyChallengeStatsResp(DailyChallengeStatsBase):
    user_id: int

    @classmethod
    def from_db(
        cls,
        obj: DailyChallengeStats,
    ) -> "DailyChallengeStatsResp":
        return cls.model_validate(obj)
