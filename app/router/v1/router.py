from __future__ import annotations

from datetime import datetime
from enum import Enum

from app.dependencies.user import v1_api_key

from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_serializer

router = APIRouter(
    prefix="/api/v1", dependencies=[Depends(v1_api_key)], tags=["V1 API"]
)


class AllStrModel(BaseModel):
    @field_serializer("*", when_used="json")
    def serialize_datetime(self, v, _info):
        if isinstance(v, Enum):
            return str(v.value)
        elif isinstance(v, datetime):
            return v.strftime("%Y-%m-%d %H:%M:%S")
        elif isinstance(v, bool):
            return "1" if v else "0"
        elif isinstance(v, list):
            return [self.serialize_datetime(item, _info) for item in v]
        return str(v)
