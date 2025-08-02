from __future__ import annotations

import datetime
from enum import Enum
from typing import Any

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    TypeAdapter,
    model_serializer,
    model_validator,
)


def serialize_msgpack(v: Any) -> Any:
    typ = v.__class__
    if issubclass(typ, BaseModel):
        return serialize_to_list(v)
    elif issubclass(typ, list):
        return TypeAdapter(
            typ, config=ConfigDict(arbitrary_types_allowed=True)
        ).dump_python(v)
    elif issubclass(typ, datetime.datetime):
        return [v, 0]
    elif issubclass(typ, Enum):
        list_ = list(typ)
        return list_.index(v) if v in list_ else v.value
    return v


def serialize_to_list(value: BaseModel) -> list[Any]:
    data = []
    for field, info in value.__class__.model_fields.items():
        data.append(serialize_msgpack(v=getattr(value, field)))
    return data


def _by_index(v: Any, class_: type[Enum]):
    enum_list = list(class_)
    if not isinstance(v, int):
        return v
    if 0 <= v < len(enum_list):
        return enum_list[v]
    raise ValueError(
        f"Value {v} is out of range for enum "
        f"{class_.__name__} with {len(enum_list)} items"
    )


def EnumByIndex(enum_class: type[Enum]) -> BeforeValidator:
    return BeforeValidator(lambda v: _by_index(v, enum_class))


def msgpack_union(v):
    data = v[1]
    data.append(v[0])
    return data


def msgpack_union_dump(v: BaseModel) -> list[Any]:
    _type = getattr(v, "type", None)
    if _type is None:
        raise ValueError(
            f"Model {v.__class__.__name__} does not have a '_type' attribute"
        )
    return [_type, serialize_to_list(v)]


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
