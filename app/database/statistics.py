from typing import TYPE_CHECKING

from app.models.score import GameMode

from sqlmodel import (
    BigInteger,
    Column,
    Field,
    ForeignKey,
    Relationship,
    SQLModel,
)

if TYPE_CHECKING:
    from .lazer_user import User


class UserStatisticsBase(SQLModel):
    mode: GameMode
    count_100: int = Field(default=0, sa_column=Column(BigInteger))
    count_300: int = Field(default=0, sa_column=Column(BigInteger))
    count_50: int = Field(default=0, sa_column=Column(BigInteger))
    count_miss: int = Field(default=0, sa_column=Column(BigInteger))

    global_rank: int | None = Field(default=None)
    country_rank: int | None = Field(default=None)

    pp: float = Field(default=0.0)
    ranked_score: int = Field(default=0)
    hit_accuracy: float = Field(default=0.00)
    total_score: int = Field(default=0, sa_column=Column(BigInteger))
    total_hits: int = Field(default=0, sa_column=Column(BigInteger))
    maximum_combo: int = Field(default=0)

    play_count: int = Field(default=0)
    play_time: int = Field(default=0, sa_column=Column(BigInteger))
    replays_watched_by_others: int = Field(default=0)
    is_ranked: bool = Field(default=True)


class UserStatistics(UserStatisticsBase, table=True):
    __tablename__ = "lazer_user_statistics"  # pyright: ignore[reportAssignmentType]
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(
        default=None,
        sa_column=Column(
            BigInteger,
            ForeignKey("lazer_users.id"),
            index=True,
        ),
    )
    grade_ss: int = Field(default=0)
    grade_ssh: int = Field(default=0)
    grade_s: int = Field(default=0)
    grade_sh: int = Field(default=0)
    grade_a: int = Field(default=0)

    level_current: int = Field(default=1)
    level_progress: int = Field(default=0)

    user: "User" = Relationship(back_populates="statistics")  # type: ignore[valid-type]


class UserStatisticsResp(UserStatisticsBase):
    grade_counts: dict[str, int] = Field(
        default_factory=lambda: {
            "ss": 0,
            "ssh": 0,
            "s": 0,
            "sh": 0,
            "a": 0,
        }
    )
    level: dict[str, int] = Field(
        default_factory=lambda: {
            "current": 1,
            "progress": 0,
        }
    )

    @classmethod
    def from_db(cls, obj: UserStatistics) -> "UserStatisticsResp":
        s = cls.model_validate(obj)
        s.grade_counts = {
            "ss": obj.grade_ss,
            "ssh": obj.grade_ssh,
            "s": obj.grade_s,
            "sh": obj.grade_sh,
            "a": obj.grade_a,
        }
        s.level = {
            "current": obj.level_current,
            "progress": obj.level_progress,
        }
        return s
