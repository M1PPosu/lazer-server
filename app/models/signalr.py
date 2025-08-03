from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, ClassVar

from pydantic import (
    BaseModel,
    BeforeValidator,
    Field,
)


@dataclass
class SignalRMeta:
    member_ignore: bool = False  # implement of IgnoreMember (msgpack) attribute
    json_ignore: bool = False  # implement of JsonIgnore (json) attribute
    use_upper_case: bool = False  # use upper CamelCase for field names


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


class SignalRUnionMessage(BaseModel):
    union_type: ClassVar[int]


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
