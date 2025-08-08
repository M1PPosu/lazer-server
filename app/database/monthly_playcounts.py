from datetime import date
from typing import TYPE_CHECKING

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


class MonthlyPlaycounts(SQLModel, table=True):
    __tablename__ = "monthly_playcounts"  # pyright: ignore[reportAssignmentType]

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    user_id: int = Field(
        sa_column=Column(BigInteger, ForeignKey("lazer_users.id"), index=True)
    )
    year: int = Field(index=True)
    month: int = Field(index=True)
    playcount: int = Field(default=0)

    user: "User" = Relationship(back_populates="monthly_playcounts")


class MonthlyPlaycountsResp(SQLModel):
    start_date: date
    count: int

    @classmethod
    def from_db(cls, db_model: MonthlyPlaycounts) -> "MonthlyPlaycountsResp":
        return cls(
            start_date=date(db_model.year, db_model.month, 1),
            count=db_model.playcount,
        )
