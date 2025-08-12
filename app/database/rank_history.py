from datetime import (
    UTC,
    date as dt,
    datetime,
)
from typing import TYPE_CHECKING, Optional

from app.models.score import GameMode

from pydantic import BaseModel
from sqlmodel import (
    BigInteger,
    Column,
    Date,
    Field,
    ForeignKey,
    Relationship,
    SQLModel,
    col,
    select,
)
from sqlmodel.ext.asyncio.session import AsyncSession

if TYPE_CHECKING:
    from .lazer_user import User


class RankHistory(SQLModel, table=True):
    __tablename__ = "rank_history"  # pyright: ignore[reportAssignmentType]

    id: int | None = Field(default=None, sa_column=Column(BigInteger, primary_key=True))
    user_id: int = Field(
        sa_column=Column(BigInteger, ForeignKey("lazer_users.id"), index=True)
    )
    mode: GameMode
    rank: int
    date: dt = Field(
        default_factory=lambda: datetime.now(UTC).date(),
        sa_column=Column(Date, index=True),
    )

    user: Optional["User"] = Relationship(back_populates="rank_history")


class RankTop(SQLModel, table=True):
    __tablename__ = "rank_top"  # pyright: ignore[reportAssignmentType]

    id: int | None = Field(default=None, sa_column=Column(BigInteger, primary_key=True))
    user_id: int = Field(
        sa_column=Column(BigInteger, ForeignKey("lazer_users.id"), index=True)
    )
    mode: GameMode
    rank: int
    date: dt = Field(
        default_factory=lambda: datetime.now(UTC).date(),
        sa_column=Column(Date, index=True),
    )


class RankHistoryResp(BaseModel):
    mode: GameMode
    data: list[int]

    @classmethod
    async def from_db(
        cls, session: AsyncSession, user_id: int, mode: GameMode
    ) -> "RankHistoryResp":
        results = (
            await session.exec(
                select(RankHistory)
                .where(RankHistory.user_id == user_id, RankHistory.mode == mode)
                .order_by(col(RankHistory.date).desc())
                .limit(90)
            )
        ).all()
        data = [result.rank for result in results]
        data.reverse()
        return cls(mode=mode, data=data)
