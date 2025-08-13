from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlmodel import (
    JSON,
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


class EventType(str, Enum):
    ACHIEVEMENT = "achievement"
    BEATMAP_PLAYCOUNT = "beatmap_playcount"
    BEATMAPSET_APPROVE = "beatmapset_approve"
    BEATMAPSET_DELETE = "beatmapset_delete"
    BEATMAPSET_REVIVE = "beatmapset_revive"
    BEATMAPSET_UPDATE = "beatmapset_update"
    BEATMAPSET_UPLOAD = "beatmapset_upload"
    RANK = "rank"
    RANK_LOST = "rank_lost"
    # 鉴于本服务器没有 supporter 这一说，这三个字段没有必要
    # USER_SUPPORT_AGAIN="user_support_again"
    # USER_SUPPORT_FIRST="user_support"
    # USER_SUPPORT_GIFT="user_support_gift"
    USERNAME_CHANGE = "username_change"


class EventBase(SQLModel):
    id: int = Field(default=None, primary_key=True)
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), default=datetime.now(UTC))
    )
    type: EventType
    event_payload: dict = Field(
        exclude=True, default_factory=dict, sa_column=Column(JSON)
    )


class Event(EventBase, table=True):
    __tablename__ = "user_events"  # pyright: ignore[reportAssignmentType]
    user_id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, ForeignKey("lazer_users.id"), index=True),
    )
    user: "User" = Relationship(back_populates="events")


class EventResp(EventBase):
    def merge_payload(self) -> "EventResp":
        for key, value in self.event_payload.items():
            setattr(self, key, value)
        return self

    pass
