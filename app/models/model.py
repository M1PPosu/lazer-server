from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, field_serializer


class UTCBaseModel(BaseModel):
    @field_serializer("*", when_used="json")
    def serialize_datetime(self, v, _info):
        if isinstance(v, datetime):
            if v.tzinfo is None:
                v = v.replace(tzinfo=UTC)
            return v.astimezone(UTC).isoformat()
        return v
