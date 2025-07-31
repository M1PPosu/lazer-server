from datetime import UTC, datetime
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


class UserAchievementBase(SQLModel, UTCBaseModel):
    achievement_id: int = Field(primary_key=True)
    achieved_at: datetime = Field(
        default=datetime.now(UTC), sa_column=Column(DateTime(timezone=True))
    )


class UserAchievement(UserAchievementBase, table=True):
    __tablename__ = "lazer_user_achievements"  # pyright: ignore[reportAssignmentType]

    id: int | None = Field(default=None, primary_key=True, index=True)
    user_id: int = Field(
        sa_column=Column(BigInteger, ForeignKey("lazer_users.id")), exclude=True
    )
    user: "User" = Relationship(back_populates="achievement")


class UserAchievementResp(UserAchievementBase):
    @classmethod
    def from_db(cls, db_model: UserAchievement) -> "UserAchievementResp":
        return cls.model_validate(db_model)
