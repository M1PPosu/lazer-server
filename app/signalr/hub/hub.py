from __future__ import annotations

from abc import abstractmethod
import asyncio
from enum import Enum
import inspect
import time
from typing import Any

from app.config import settings
from app.exception import InvokeException
from app.log import logger
from app.models.signalr import UserState, _by_index
from app.signalr.packet import (
    ClosePacket,
    CompletionPacket,
    InvocationPacket,
    Packet,
    PingPacket,
    Protocol,
)
from app.signalr.store import ResultStore
from app.signalr.utils import get_signature

from fastapi import WebSocket
from pydantic import BaseModel
from starlette.websockets import WebSocketDisconnect


class CloseConnection(Exception):
    def __init__(
        self,
        message: str = "Connection closed",
        allow_reconnect: bool = False,
        from_client: bool = False,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.allow_reconnect = allow_reconnect
        self.from_client = from_client


class Client:
    def __init__(
        self,
        connection_id: str,
        connection_token: str,
        connection: WebSocket,
        protocol: Protocol,
    ) -> None:
        self.connection_id = connection_id
        self.connection_token = connection_token
        self.connection = connection
        self.procotol = protocol
        self._listen_task: asyncio.Task | None = None
        self._ping_task: asyncio.Task | None = None
        self._store = ResultStore()

    def __hash__(self) -> int:
        return hash(self.connection_token)

    @property
    def user_id(self) -> int:
        return int(self.connection_id)

    async def send_packet(self, packet: Packet):
        await self.connection.send_bytes(self.procotol.encode(packet))

    async def receive_packets(self) -> list[Packet]:
        message = await self.connection.receive()
        d = message.get("bytes") or message.get("text", "").encode()
        if not d:
            return []
        return self.procotol.decode(d)

    async def _ping(self):
        while True:
            try:
                await self.send_packet(PingPacket())
                await asyncio.sleep(settings.SIGNALR_PING_INTERVAL)
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error in ping task for {self.connection_id}: {e}")
                break


class Hub[TState: UserState]:
    def __init__(self) -> None:
        self.clients: dict[str, Client] = {}
        self.waited_clients: dict[str, int] = {}
        self.tasks: set[asyncio.Task] = set()
        self.groups: dict[str, set[Client]] = {}
        self.state: dict[int, TState] = {}

    def add_waited_client(self, connection_token: str, timestamp: int) -> None:
        self.waited_clients[connection_token] = timestamp

    def get_client_by_id(self, id: str, default: Any = None) -> Client:
        for client in self.clients.values():
            if client.connection_id == id:
                return client
        return default

    @abstractmethod
    def create_state(self, client: Client) -> TState:
        raise NotImplementedError

    def get_or_create_state(self, client: Client) -> TState:
        if (state := self.state.get(client.user_id)) is not None:
            return state
        state = self.create_state(client)
        self.state[client.user_id] = state
        return state

    def add_to_group(self, client: Client, group_id: str) -> None:
        self.groups.setdefault(group_id, set()).add(client)

    def remove_from_group(self, client: Client, group_id: str) -> None:
        if group_id in self.groups:
            self.groups[group_id].discard(client)

    async def add_client(
        self,
        connection_id: str,
        connection_token: str,
        protocol: Protocol,
        connection: WebSocket,
    ) -> Client:
        if connection_token in self.clients:
            raise ValueError(
                f"Client with connection token {connection_token} already exists."
            )
        if connection_token in self.waited_clients:
            if (
                self.waited_clients[connection_token]
                < time.time() - settings.SIGNALR_NEGOTIATE_TIMEOUT
            ):
                raise TimeoutError(f"Connection {connection_id} has waited too long.")
            del self.waited_clients[connection_token]
        client = Client(connection_id, connection_token, connection, protocol)
        self.clients[connection_token] = client
        task = asyncio.create_task(client._ping())
        self.tasks.add(task)
        client._ping_task = task
        return client

    async def remove_client(self, client: Client) -> None:
        del self.clients[client.connection_token]
        if client._listen_task:
            client._listen_task.cancel()
        if client._ping_task:
            client._ping_task.cancel()
        for group in self.groups.values():
            group.discard(client)
        await self.clean_state(client, False)

    @abstractmethod
    async def _clean_state(self, state: TState) -> None:
        return

    async def clean_state(self, client: Client, disconnected: bool) -> None:
        if (state := self.state.get(client.user_id)) is None:
            return
        if disconnected and client.connection_token != state.connection_token:
            return
        try:
            await self._clean_state(state)
        except Exception:
            ...

    async def on_connect(self, client: Client) -> None:
        if method := getattr(self, "on_client_connect", None):
            await method(client)

    async def send_packet(self, client: Client, packet: Packet) -> None:
        await client.send_packet(packet)

    async def broadcast_call(self, method: str, *args: Any) -> None:
        tasks = []
        for client in self.clients.values():
            tasks.append(self.call_noblock(client, method, *args))
        await asyncio.gather(*tasks)

    async def broadcast_group_call(
        self, group_id: str, method: str, *args: Any
    ) -> None:
        tasks = []
        for client in self.groups.get(group_id, []):
            tasks.append(self.call_noblock(client, method, *args))
        await asyncio.gather(*tasks)

    async def _listen_client(self, client: Client) -> None:
        try:
            while True:
                packets = await client.receive_packets()
                for packet in packets:
                    if isinstance(packet, PingPacket):
                        continue
                    elif isinstance(packet, ClosePacket):
                        raise CloseConnection(
                            packet.error or "Connection closed by client",
                            packet.allow_reconnect,
                            True,
                        )
                    task = asyncio.create_task(self._handle_packet(client, packet))
                    self.tasks.add(task)
                    task.add_done_callback(self.tasks.discard)
        except WebSocketDisconnect as e:
            logger.info(
                f"Client {client.connection_id} disconnected: {e.code}, {e.reason}"
            )
        except RuntimeError as e:
            if "disconnect message" in str(e):
                logger.info(f"Client {client.connection_id} closed the connection.")
            else:
                logger.exception(f"RuntimeError in client {client.connection_id}: {e}")
        except CloseConnection as e:
            if not e.from_client:
                await client.send_packet(
                    ClosePacket(error=e.message, allow_reconnect=e.allow_reconnect)
                )
            logger.info(
                f"Client {client.connection_id} closed the connection: {e.message}"
            )
        except Exception:
            logger.exception(f"Error in client {client.connection_id}")

        await self.remove_client(client)

    async def _handle_packet(self, client: Client, packet: Packet) -> None:
        if isinstance(packet, PingPacket):
            return
        elif isinstance(packet, InvocationPacket):
            args = packet.arguments or []
            error = None
            result = None
            try:
                result = await self.invoke_method(client, packet.target, args)
            except InvokeException as e:
                error = e.message
            except Exception as e:
                logger.exception(
                    f"Error invoking method {packet.target} for "
                    f"client {client.connection_id}"
                )
                error = str(e)
            if packet.invocation_id is not None:
                await client.send_packet(
                    CompletionPacket(
                        invocation_id=packet.invocation_id,
                        error=error,
                        result=result,
                    )
                )
        elif isinstance(packet, CompletionPacket):
            client._store.add_result(packet.invocation_id, packet.result, packet.error)

    async def invoke_method(self, client: Client, method: str, args: list[Any]) -> Any:
        method_ = getattr(self, method, None)
        call_params = []
        if not method_:
            raise InvokeException(f"Method '{method}' not found in hub.")
        signature = get_signature(method_)
        for name, param in signature.parameters.items():
            if name == "self" or param.annotation is Client:
                continue
            if issubclass(param.annotation, BaseModel):
                call_params.append(param.annotation.model_validate(args.pop(0)))
            elif inspect.isclass(param.annotation) and issubclass(
                param.annotation, Enum
            ):
                call_params.append(_by_index(args.pop(0), param.annotation))
            else:
                call_params.append(args.pop(0))
        return await method_(client, *call_params)

    async def call(self, client: Client, method: str, *args: Any) -> Any:
        invocation_id = client._store.get_invocation_id()
        await client.send_packet(
            InvocationPacket(
                header={},
                invocation_id=invocation_id,
                target=method,
                arguments=list(args),
                stream_ids=None,
            )
        )
        r = await client._store.fetch(invocation_id, None)
        if r[1]:
            raise InvokeException(r[1])
        return r[0]

    async def call_noblock(self, client: Client, method: str, *args: Any) -> None:
        await client.send_packet(
            InvocationPacket(
                header={},
                invocation_id=None,
                target=method,
                arguments=list(args),
                stream_ids=None,
            )
        )
        return None

    def __contains__(self, item: str) -> bool:
        return item in self.clients or item in self.waited_clients
