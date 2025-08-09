from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncAttrs
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
    from .room import Room


class RoomParticipatedUser(AsyncAttrs, SQLModel, table=True):
    __tablename__ = "room_participated_users"  # pyright: ignore[reportAssignmentType]

    id: int | None = Field(
        default=None, sa_column=Column(BigInteger, primary_key=True, autoincrement=True)
    )
    room_id: int = Field(sa_column=Column(ForeignKey("rooms.id"), nullable=False))
    user_id: int = Field(
        sa_column=Column(BigInteger, ForeignKey("lazer_users.id"), nullable=False)
    )
    joined_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default=datetime.now(UTC),
    )
    left_at: datetime | None = Field(
        sa_column=Column(DateTime(timezone=True), nullable=True), default=None
    )

    room: "Room" = Relationship()
    user: "User" = Relationship()
