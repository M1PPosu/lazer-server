from __future__ import annotations

from dataclasses import dataclass
import datetime
from enum import Enum, IntEnum
import inspect
import json
from types import NoneType, UnionType
from typing import (
    Any,
    Protocol as TypingProtocol,
    Union,
    get_args,
    get_origin,
)

from app.models.signalr import SignalRMeta, SignalRUnionMessage
from app.utils import camel_to_snake, snake_to_camel, snake_to_pascal

import msgpack_lazer_api as m
from pydantic import BaseModel

SEP = b"\x1e"


class PacketType(IntEnum):
    INVOCATION = 1
    STREAM_ITEM = 2
    COMPLETION = 3
    STREAM_INVOCATION = 4
    CANCEL_INVOCATION = 5
    PING = 6
    CLOSE = 7


@dataclass(kw_only=True)
class Packet:
    type: PacketType
    header: dict[str, Any] | None = None


@dataclass(kw_only=True)
class InvocationPacket(Packet):
    type: PacketType = PacketType.INVOCATION
    invocation_id: str | None
    target: str
    arguments: list[Any] | None = None
    stream_ids: list[str] | None = None


@dataclass(kw_only=True)
class CompletionPacket(Packet):
    type: PacketType = PacketType.COMPLETION
    invocation_id: str
    result: Any
    error: str | None = None


@dataclass(kw_only=True)
class PingPacket(Packet):
    type: PacketType = PacketType.PING


@dataclass(kw_only=True)
class ClosePacket(Packet):
    type: PacketType = PacketType.CLOSE
    error: str | None = None
    allow_reconnect: bool = False


PACKETS = {
    PacketType.INVOCATION: InvocationPacket,
    PacketType.COMPLETION: CompletionPacket,
    PacketType.PING: PingPacket,
    PacketType.CLOSE: ClosePacket,
}


class Protocol(TypingProtocol):
    @staticmethod
    def decode(input: bytes) -> list[Packet]: ...

    @staticmethod
    def encode(packet: Packet) -> bytes: ...

    @classmethod
    def validate_object(cls, v: Any, typ: type) -> Any: ...


class MsgpackProtocol:
    @classmethod
    def serialize_msgpack(cls, v: Any) -> Any:
        typ = v.__class__
        if issubclass(typ, BaseModel):
            return cls.serialize_to_list(v)
        elif issubclass(typ, list):
            return [cls.serialize_msgpack(item) for item in v]
        elif issubclass(typ, datetime.datetime):
            return [v, 0]
        elif issubclass(typ, datetime.timedelta):
            return int(v.total_seconds() * 10_000_000)
        elif isinstance(v, dict):
            return {
                cls.serialize_msgpack(k): cls.serialize_msgpack(value)
                for k, value in v.items()
            }
        elif issubclass(typ, Enum):
            list_ = list(typ)
            return list_.index(v) if v in list_ else v.value
        return v

    @classmethod
    def serialize_to_list(cls, value: BaseModel) -> list[Any]:
        values = []
        for field, info in value.__class__.model_fields.items():
            metadata = next(
                (m for m in info.metadata if isinstance(m, SignalRMeta)), None
            )
            if metadata and metadata.member_ignore:
                continue
            values.append(cls.serialize_msgpack(v=getattr(value, field)))
        if issubclass(value.__class__, SignalRUnionMessage):
            return [value.__class__.union_type, values]
        else:
            return values

    @staticmethod
    def process_object(v: Any, typ: type[BaseModel]) -> Any:
        if isinstance(v, list):
            d = {}
            i = 0
            for field, info in typ.model_fields.items():
                metadata = next(
                    (m for m in info.metadata if isinstance(m, SignalRMeta)), None
                )
                if metadata and metadata.member_ignore:
                    continue
                anno = info.annotation
                if anno is None:
                    d[camel_to_snake(field)] = v[i]
                else:
                    d[field] = MsgpackProtocol.validate_object(v[i], anno)
                i += 1
            return d
        return v

    @staticmethod
    def _encode_varint(value: int) -> bytes:
        result = []
        while value >= 0x80:
            result.append((value & 0x7F) | 0x80)
            value >>= 7
        result.append(value & 0x7F)
        return bytes(result)

    @staticmethod
    def _decode_varint(data: bytes, offset: int = 0) -> tuple[int, int]:
        result = 0
        shift = 0
        pos = offset

        while pos < len(data):
            byte = data[pos]
            result |= (byte & 0x7F) << shift
            pos += 1
            if (byte & 0x80) == 0:
                break
            shift += 7

        return result, pos

    @staticmethod
    def decode(input: bytes) -> list[Packet]:
        length, offset = MsgpackProtocol._decode_varint(input)
        message_data = input[offset : offset + length]
        unpacked = m.decode(message_data)
        packet_type = PacketType(unpacked[0])
        if packet_type not in PACKETS:
            raise ValueError(f"Unknown packet type: {packet_type}")
        match packet_type:
            case PacketType.INVOCATION:
                return [
                    InvocationPacket(
                        header=unpacked[1],
                        invocation_id=unpacked[2],
                        target=unpacked[3],
                        arguments=unpacked[4] if len(unpacked) > 4 else None,
                        stream_ids=unpacked[5] if len(unpacked) > 5 else None,
                    )
                ]
            case PacketType.COMPLETION:
                result_kind = unpacked[3]
                return [
                    CompletionPacket(
                        header=unpacked[1],
                        invocation_id=unpacked[2],
                        error=unpacked[4] if result_kind == 1 else None,
                        result=unpacked[5] if result_kind == 3 else None,
                    )
                ]
            case PacketType.PING:
                return [PingPacket()]
            case PacketType.CLOSE:
                return [
                    ClosePacket(
                        error=unpacked[1],
                        allow_reconnect=unpacked[2] if len(unpacked) > 2 else False,
                    )
                ]
        raise ValueError(f"Unsupported packet type: {packet_type}")

    @classmethod
    def validate_object(cls, v: Any, typ: type) -> Any:
        if issubclass(typ, BaseModel):
            return typ.model_validate(obj=cls.process_object(v, typ))
        elif inspect.isclass(typ) and issubclass(typ, datetime.datetime):
            return v[0]
        elif inspect.isclass(typ) and issubclass(typ, datetime.timedelta):
            return datetime.timedelta(seconds=int(v / 10_000_000))
        elif get_origin(typ) is list:
            return [cls.validate_object(item, get_args(typ)[0]) for item in v]
        elif inspect.isclass(typ) and issubclass(typ, Enum):
            list_ = list(typ)
            return list_[v] if isinstance(v, int) and 0 <= v < len(list_) else typ(v)
        elif get_origin(typ) is dict:
            return {
                cls.validate_object(k, get_args(typ)[0]): cls.validate_object(
                    v, get_args(typ)[1]
                )
                for k, v in v.items()
            }
        elif (origin := get_origin(typ)) is Union or origin is UnionType:
            args = get_args(typ)
            if len(args) == 2 and NoneType in args:
                non_none_args = [arg for arg in args if arg is not NoneType]
                if len(non_none_args) == 1:
                    if v is None:
                        return None
                    return cls.validate_object(v, non_none_args[0])

            # suppose use `MessagePack-CSharp Union | None`
            # except `X (Other Type) | None`
            if NoneType in args and v is None:
                return None
            if not all(
                issubclass(arg, SignalRUnionMessage) or arg is NoneType for arg in args
            ):
                raise ValueError(
                    f"Cannot validate {v} to {typ}, "
                    "only SignalRUnionMessage subclasses are supported"
                )
            union_type = v[0]
            for arg in args:
                assert issubclass(arg, SignalRUnionMessage)
                if arg.union_type == union_type:
                    return cls.validate_object(v[1], arg)
        return v

    @staticmethod
    def encode(packet: Packet) -> bytes:
        payload = [packet.type.value, packet.header or {}]
        if isinstance(packet, InvocationPacket):
            payload.extend(
                [
                    packet.invocation_id,
                    packet.target,
                ]
            )
            if packet.arguments is not None:
                payload.append(
                    [MsgpackProtocol.serialize_msgpack(arg) for arg in packet.arguments]
                )
            if packet.stream_ids is not None:
                payload.append(packet.stream_ids)
        elif isinstance(packet, CompletionPacket):
            result_kind = 2
            if packet.error:
                result_kind = 1
            elif packet.result is not None:
                result_kind = 3
            payload.extend(
                [
                    packet.invocation_id,
                    result_kind,
                    packet.error
                    or MsgpackProtocol.serialize_msgpack(packet.result)
                    or None,
                ]
            )
        elif isinstance(packet, ClosePacket):
            payload.extend(
                [
                    packet.error or "",
                    packet.allow_reconnect,
                ]
            )
        elif isinstance(packet, PingPacket):
            payload.pop(-1)
        data = m.encode(payload)
        return MsgpackProtocol._encode_varint(len(data)) + data


class JSONProtocol:
    @classmethod
    def serialize_to_json(cls, v: Any, dict_key: bool = False, in_union: bool = False):
        typ = v.__class__
        if issubclass(typ, BaseModel):
            return cls.serialize_model(v, in_union)
        elif isinstance(v, dict):
            return {
                cls.serialize_to_json(k, True): cls.serialize_to_json(value)
                for k, value in v.items()
            }
        elif isinstance(v, list):
            return [cls.serialize_to_json(item) for item in v]
        elif isinstance(v, datetime.datetime):
            return v.isoformat()
        elif isinstance(v, datetime.timedelta):
            # d.hh:mm:ss
            total_seconds = int(v.total_seconds())
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            return f"{hours:02}:{minutes:02}:{seconds:02}"
        elif isinstance(v, Enum) and dict_key:
            return v.value
        elif isinstance(v, Enum):
            list_ = list(typ)
            return list_.index(v)
        return v

    @classmethod
    def serialize_model(cls, v: BaseModel, in_union: bool = False) -> dict[str, Any]:
        d = {}
        is_union = issubclass(v.__class__, SignalRUnionMessage)
        for field, info in v.__class__.model_fields.items():
            metadata = next(
                (m for m in info.metadata if isinstance(m, SignalRMeta)), None
            )
            if metadata and metadata.json_ignore:
                continue
            name = (
                snake_to_camel(
                    field,
                    metadata.use_abbr if metadata else True,
                )
                if not is_union
                else snake_to_pascal(
                    field,
                    metadata.use_abbr if metadata else True,
                )
            )
            d[name] = cls.serialize_to_json(getattr(v, field), in_union=is_union)
        if is_union and not in_union:
            return {
                "$dtype": v.__class__.__name__,
                "$value": d,
            }
        return d

    @staticmethod
    def process_object(
        v: Any, typ: type[BaseModel], from_union: bool = False
    ) -> dict[str, Any]:
        d = {}
        for field, info in typ.model_fields.items():
            metadata = next(
                (m for m in info.metadata if isinstance(m, SignalRMeta)), None
            )
            if metadata and metadata.json_ignore:
                continue
            name = (
                snake_to_camel(field, metadata.use_abbr if metadata else True)
                if not from_union
                else snake_to_pascal(field, metadata.use_abbr if metadata else True)
            )
            value = v.get(name)
            anno = typ.model_fields[field].annotation
            if anno is None:
                d[field] = value
                continue
            d[field] = JSONProtocol.validate_object(value, anno)
        return d

    @staticmethod
    def decode(input: bytes) -> list[Packet]:
        packets_raw = input.removesuffix(SEP).split(SEP)
        packets = []
        if len(packets_raw) > 1:
            for packet_raw in packets_raw:
                packets.extend(JSONProtocol.decode(packet_raw))
            return packets
        else:
            data = json.loads(packets_raw[0])
            packet_type = PacketType(data["type"])
            if packet_type not in PACKETS:
                raise ValueError(f"Unknown packet type: {packet_type}")
            match packet_type:
                case PacketType.INVOCATION:
                    return [
                        InvocationPacket(
                            header=data.get("header"),
                            invocation_id=data.get("invocationId"),
                            target=data["target"],
                            arguments=data.get("arguments"),
                            stream_ids=data.get("streamIds"),
                        )
                    ]
                case PacketType.COMPLETION:
                    return [
                        CompletionPacket(
                            header=data.get("header"),
                            invocation_id=data["invocationId"],
                            error=data.get("error"),
                            result=data.get("result"),
                        )
                    ]
                case PacketType.PING:
                    return [PingPacket()]
                case PacketType.CLOSE:
                    return [
                        ClosePacket(
                            error=data.get("error"),
                            allow_reconnect=data.get("allowReconnect", False),
                        )
                    ]
            raise ValueError(f"Unsupported packet type: {packet_type}")

    @classmethod
    def validate_object(cls, v: Any, typ: type, from_union: bool = False) -> Any:
        if issubclass(typ, BaseModel):
            return typ.model_validate(JSONProtocol.process_object(v, typ, from_union))
        elif inspect.isclass(typ) and issubclass(typ, datetime.datetime):
            return datetime.datetime.fromisoformat(v)
        elif inspect.isclass(typ) and issubclass(typ, datetime.timedelta):
            # d.hh:mm:ss
            parts = v.split(":")
            if len(parts) == 3:
                return datetime.timedelta(
                    hours=int(parts[0]), minutes=int(parts[1]), seconds=int(parts[2])
                )
            elif len(parts) == 2:
                return datetime.timedelta(minutes=int(parts[0]), seconds=int(parts[1]))
            elif len(parts) == 1:
                return datetime.timedelta(seconds=int(parts[0]))
        elif get_origin(typ) is list:
            return [cls.validate_object(item, get_args(typ)[0]) for item in v]
        elif inspect.isclass(typ) and issubclass(typ, Enum):
            list_ = list(typ)
            return list_[v] if isinstance(v, int) and 0 <= v < len(list_) else typ(v)
        elif get_origin(typ) is dict:
            return {
                cls.validate_object(k, get_args(typ)[0]): cls.validate_object(
                    v, get_args(typ)[1]
                )
                for k, v in v.items()
            }
        elif (origin := get_origin(typ)) is Union or origin is UnionType:
            args = get_args(typ)
            if len(args) == 2 and NoneType in args:
                non_none_args = [arg for arg in args if arg is not NoneType]
                if len(non_none_args) == 1:
                    if v is None:
                        return None
                    return cls.validate_object(v, non_none_args[0])

            # suppose use `MessagePack-CSharp Union | None`
            # except `X (Other Type) | None`
            if NoneType in args and v is None:
                return None
            if not all(
                issubclass(arg, SignalRUnionMessage) or arg is NoneType for arg in args
            ):
                raise ValueError(
                    f"Cannot validate {v} to {typ}, "
                    "only SignalRUnionMessage subclasses are supported"
                )
            # https://github.com/ppy/osu/blob/98acd9/osu.Game/Online/SignalRDerivedTypeWorkaroundJsonConverter.cs
            union_type = v["$dtype"]
            for arg in args:
                assert issubclass(arg, SignalRUnionMessage)
                if arg.__name__ == union_type:
                    return cls.validate_object(v["$value"], arg, True)
        return v

    @staticmethod
    def encode(packet: Packet) -> bytes:
        payload: dict[str, Any] = {
            "type": packet.type.value,
        }
        if packet.header:
            payload["header"] = packet.header
        if isinstance(packet, InvocationPacket):
            payload.update(
                {
                    "target": packet.target,
                }
            )
            if packet.invocation_id is not None:
                payload["invocationId"] = packet.invocation_id
            if packet.arguments is not None:
                payload["arguments"] = [
                    JSONProtocol.serialize_to_json(arg) for arg in packet.arguments
                ]
            if packet.stream_ids is not None:
                payload["streamIds"] = packet.stream_ids
        elif isinstance(packet, CompletionPacket):
            payload.update(
                {
                    "invocationId": packet.invocation_id,
                }
            )
            if packet.error is not None:
                payload["error"] = packet.error
            if packet.result is not None:
                payload["result"] = JSONProtocol.serialize_to_json(packet.result)
        elif isinstance(packet, PingPacket):
            pass
        elif isinstance(packet, ClosePacket):
            payload.update(
                {
                    "allowReconnect": packet.allow_reconnect,
                }
            )
            if packet.error is not None:
                payload["error"] = packet.error
        return json.dumps(payload).encode("utf-8") + SEP


PROTOCOLS: dict[str, Protocol] = {
    "json": JSONProtocol,
    "messagepack": MsgpackProtocol,
}
