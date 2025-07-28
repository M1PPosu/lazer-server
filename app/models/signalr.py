from __future__ import annotations

import datetime
from typing import Any, get_origin

import msgpack
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    model_serializer,
    model_validator,
)


def serialize_to_list(value: BaseModel) -> list[Any]:
    data = []
    for field, info in value.__class__.model_fields.items():
        v = getattr(value, field)
        anno = get_origin(info.annotation)
        if anno and issubclass(anno, BaseModel):
            data.append(serialize_to_list(v))
        elif anno and issubclass(anno, list):
            data.append(
                TypeAdapter(
                    info.annotation,
                ).dump_python(v)
            )
        elif isinstance(v, datetime.datetime):
            data.append([msgpack.ext.Timestamp.from_datetime(v), 0])
        else:
            data.append(v)
    return data


class MessagePackArrayModel(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    @model_validator(mode="before")
    @classmethod
    def unpack(cls, v: Any) -> Any:
        if isinstance(v, list):
            fields = list(cls.model_fields.keys())
            if len(v) != len(fields):
                raise ValueError(f"Expected list of length {len(fields)}, got {len(v)}")
            return dict(zip(fields, v))
        return v

    @model_serializer
    def serialize(self) -> list[Any]:
        return serialize_to_list(self)


class Transport(BaseModel):
    transport: str
    transfer_formats: list[str] = Field(
        default_factory=lambda: ["Binary", "Text"], alias="transferFormats"
    )


class NegotiateResponse(BaseModel):
    connectionId: str
    connectionToken: str
    negotiateVersion: int = 1
    availableTransports: list[Transport]


class UserState(BaseModel):
    connection_id: str
    connection_token: str
