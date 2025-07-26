from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .user import User


class OAuthToken(SQLModel, table=True):
    __tablename__ = "oauth_tokens"  # pyright: ignore[reportAssignmentType]

    id: int | None = Field(default=None, primary_key=True, index=True)
    user_id: int = Field(foreign_key="users.id")
    access_token: str = Field(max_length=500, unique=True)
    refresh_token: str = Field(max_length=500, unique=True)
    token_type: str = Field(default="Bearer", max_length=20)
    scope: str = Field(default="*", max_length=100)
    expires_at: datetime = Field(sa_column=Column(DateTime))
    created_at: datetime = Field(
        default_factory=datetime.utcnow, sa_column=Column(DateTime)
    )

    user: "User" = Relationship()
