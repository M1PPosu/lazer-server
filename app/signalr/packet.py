from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
import json
from typing import (
    Any,
    Protocol as TypingProtocol,
)

import msgpack

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


PACKETS = {
    PacketType.INVOCATION: InvocationPacket,
    PacketType.COMPLETION: CompletionPacket,
    PacketType.PING: PingPacket,
}


class Protocol(TypingProtocol):
    @staticmethod
    def decode(input: bytes) -> list[Packet]: ...

    @staticmethod
    def encode(packet: Packet) -> bytes: ...


class MsgpackProtocol:
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
        # FIXME: custom deserializer for APIMod
        # https://github.com/ppy/osu/blob/master/osu.Game/Online/API/ModSettingsDictionaryFormatter.cs
        unpacked = msgpack.unpackb(
            message_data, raw=False, strict_map_key=False, use_list=True
        )
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
        raise ValueError(f"Unsupported packet type: {packet_type}")

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
                payload.append(packet.arguments)
            if packet.stream_ids is not None:
                payload.append(packet.stream_ids)
        elif isinstance(packet, CompletionPacket):
            result_kind = 2
            if packet.error:
                result_kind = 1
            elif packet.result is None:
                result_kind = 3
            payload.extend(
                [
                    packet.invocation_id,
                    result_kind,
                    packet.error or packet.result or None,
                ]
            )
        elif isinstance(packet, PingPacket):
            payload.pop(-1)
        data = msgpack.packb(payload, use_bin_type=True, datetime=True)
        return MsgpackProtocol._encode_varint(len(data)) + data


class JSONProtocol:
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
            raise ValueError(f"Unsupported packet type: {packet_type}")

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
                payload["arguments"] = packet.arguments
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
                payload["result"] = packet.result
        elif isinstance(packet, PingPacket):
            pass
        return json.dumps(payload).encode("utf-8") + SEP


PROTOCOLS: dict[str, Protocol] = {
    "json": JSONProtocol,
    "messagepack": MsgpackProtocol,
}
