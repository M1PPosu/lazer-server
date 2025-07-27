from __future__ import annotations

import asyncio
import time
import traceback
from typing import Any

from app.config import settings
from app.signalr.exception import InvokeException
from app.signalr.packet import (
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
        return hash(self.connection_id + self.connection_token)

    async def send_packet(self, packet: Packet):
        await self.connection.send_bytes(self.procotol.encode(packet))

    async def receive_packet(self) -> Packet:
        message = await self.connection.receive()
        d = message.get("bytes") or message.get("text", "").encode()
        if not d:
            raise WebSocketDisconnect(code=1008, reason="Empty message received.")
        return self.procotol.decode(d)

    async def _ping(self):
        while True:
            try:
                await self.send_packet(PingPacket())
                await asyncio.sleep(settings.SIGNALR_PING_INTERVAL)
            except WebSocketDisconnect:
                break
            except Exception as e:
                print(f"Error in ping task for {self.connection_id}: {e}")
                break


class Hub:
    def __init__(self) -> None:
        self.clients: dict[str, Client] = {}
        self.waited_clients: dict[str, int] = {}
        self.tasks: set[asyncio.Task] = set()
        self.groups: dict[str, set[Client]] = {}

    def add_waited_client(self, connection_token: str, timestamp: int) -> None:
        self.waited_clients[connection_token] = timestamp

    def get_client_by_id(self, id: str, default: Any = None) -> Client:
        for client in self.clients.values():
            if client.connection_id == id:
                return client
        return default

    def add_client(
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

    async def remove_client(self, connection_id: str) -> None:
        if client := self.clients.get(connection_id):
            del self.clients[connection_id]
            if client._listen_task:
                client._listen_task.cancel()
            if client._ping_task:
                client._ping_task.cancel()
            await client.connection.close()

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
        jump = False
        while not jump:
            try:
                packet = await client.receive_packet()
                task = asyncio.create_task(self._handle_packet(client, packet))
                self.tasks.add(task)
                task.add_done_callback(self.tasks.discard)
            except WebSocketDisconnect as e:
                print(
                    f"Client {client.connection_id} disconnected: {e.code}, {e.reason}"
                )
                jump = True
            except Exception as e:
                traceback.print_exc()
                print(f"Error in client {client.connection_id}: {e}")
                jump = True
        await self.remove_client(client.connection_id)

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
                traceback.print_exc()
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
