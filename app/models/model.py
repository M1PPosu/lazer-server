from __future__ import annotations

from datetime import UTC, datetime

from app.models.score import GameMode

from pydantic import BaseModel, field_serializer


class UTCBaseModel(BaseModel):
    @field_serializer("*", when_used="json")
    def serialize_datetime(self, v, _info):
        if isinstance(v, datetime):
            if v.tzinfo is None:
                v = v.replace(tzinfo=UTC)
            return v.astimezone(UTC).isoformat()
        return v


Cursor = dict[str, int]


class RespWithCursor(BaseModel):
    cursor: Cursor | None = None


class PinAttributes(BaseModel):
    is_pinned: bool
    score_id: int


class CurrentUserAttributes(BaseModel):
    can_beatmap_update_owner: bool | None = None
    can_delete: bool | None = None
    can_edit_metadata: bool | None = None
    can_edit_tags: bool | None = None
    can_hype: bool | None = None
    can_hype_reason: str | None = None
    can_love: bool | None = None
    can_remove_from_loved: bool | None = None
    is_watching: bool | None = None
    new_hype_time: datetime | None = None
    nomination_modes: list[GameMode] | None = None
    remaining_hype: int | None = None
    can_destroy: bool | None = None
    can_reopen: bool | None = None
    can_moderate_kudosu: bool | None = None
    can_resolve: bool | None = None
    vote_score: int | None = None
    can_message: bool | None = None
    can_message_error: str | None = None
    last_read_id: int | None = None
    can_new_comment: bool | None = None
    can_new_comment_reason: str | None = None
    pin: PinAttributes | None = None
