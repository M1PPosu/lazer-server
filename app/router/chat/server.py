from __future__ import annotations

import asyncio

from app.database.chat import ChannelType, ChatChannel, ChatChannelResp, ChatMessageResp
from app.database.lazer_user import User
from app.dependencies.database import (
    DBFactory,
    engine,
    get_db_factory,
    get_redis,
)
from app.dependencies.user import get_current_user
from app.log import logger
from app.models.chat import ChatEvent
from app.service.subscribers.chat import ChatSubscriber

from fastapi import APIRouter, Depends, Header, WebSocket, WebSocketDisconnect
from fastapi.security import SecurityScopes
from fastapi.websockets import WebSocketState
from redis.asyncio import Redis
from sqlmodel.ext.asyncio.session import AsyncSession


class ChatServer:
    def __init__(self):
        self.connect_client: dict[int, WebSocket] = {}
        self.channels: dict[int, list[int]] = {}
        self.redis: Redis = get_redis()

        self.tasks: set[asyncio.Task] = set()
        self.ChatSubscriber = ChatSubscriber()
        self.ChatSubscriber.chat_server = self
        self._subscribed = False

    def _add_task(self, task):
        task = asyncio.create_task(task)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    def connect(self, user_id: int, client: WebSocket):
        self.connect_client[user_id] = client

    def get_user_joined_channel(self, user_id: int) -> list[int]:
        return [
            channel_id
            for channel_id, users in self.channels.items()
            if user_id in users
        ]

    async def disconnect(self, user: User, session: AsyncSession):
        user_id = user.id
        if user_id in self.connect_client:
            del self.connect_client[user_id]
        for channel_id, channel in self.channels.items():
            if user_id in channel:
                channel.remove(user_id)
                channel = await ChatChannel.get(channel_id, session)
                if channel:
                    await self.leave_channel(user, channel, session)

    async def send_event(self, client: WebSocket, event: ChatEvent):
        if client.client_state == WebSocketState.CONNECTED:
            await client.send_text(event.model_dump_json())

    async def broadcast(self, channel_id: int, event: ChatEvent):
        for user_id in self.channels.get(channel_id, []):
            client = self.connect_client.get(user_id)
            if client:
                await self.send_event(client, event)

    async def mark_as_read(self, channel_id: int, message_id: int):
        await self.redis.set(f"chat:{channel_id}:last_msg", message_id)

    async def send_message_to_channel(self, message: ChatMessageResp):
        self._add_task(
            self.broadcast(
                message.channel_id,
                ChatEvent(
                    event="chat.message.new",
                    data={"messages": [message], "users": [message.sender]},
                ),
            )
        )
        assert message.message_id
        await self.mark_as_read(message.channel_id, message.message_id)

    async def batch_join_channel(
        self, users: list[User], channel: ChatChannel, session: AsyncSession
    ):
        channel_id = channel.channel_id
        assert channel_id is not None

        if channel_id not in self.channels:
            self.channels[channel_id] = []
        for user_id in [user.id for user in users]:
            assert user_id is not None
            if user_id not in self.channels[channel_id]:
                self.channels[channel_id].append(user_id)

        for user in users:
            assert user.id is not None
            channel_resp = await ChatChannelResp.from_db(
                channel,
                session,
                user,
                self.redis,
                self.channels[channel_id]
                if channel.type != ChannelType.PUBLIC
                else None,
            )
            client = self.connect_client.get(user.id)
            if client:
                await self.send_event(
                    client,
                    ChatEvent(
                        event="chat.channel.join",
                        data=channel_resp.model_dump(),
                    ),
                )

    async def join_channel(
        self, user: User, channel: ChatChannel, session: AsyncSession
    ) -> ChatChannelResp:
        user_id = user.id
        channel_id = channel.channel_id
        assert channel_id is not None
        assert user_id is not None

        if channel_id not in self.channels:
            self.channels[channel_id] = []
        if user_id not in self.channels[channel_id]:
            self.channels[channel_id].append(user_id)

        channel_resp = await ChatChannelResp.from_db(
            channel,
            session,
            user,
            self.redis,
            self.channels[channel_id] if channel.type != ChannelType.PUBLIC else None,
        )

        client = self.connect_client.get(user_id)
        if client:
            await self.send_event(
                client,
                ChatEvent(
                    event="chat.channel.join",
                    data=channel_resp.model_dump(),
                ),
            )

        return channel_resp

    async def leave_channel(
        self, user: User, channel: ChatChannel, session: AsyncSession
    ) -> None:
        user_id = user.id
        channel_id = channel.channel_id
        assert channel_id is not None
        assert user_id is not None

        if channel_id in self.channels and user_id in self.channels[channel_id]:
            self.channels[channel_id].remove(user_id)

        if (c := self.channels.get(channel_id)) is not None and not c:
            del self.channels[channel_id]

        channel_resp = await ChatChannelResp.from_db(
            channel,
            session,
            user,
            self.redis,
            self.channels.get(channel_id)
            if channel.type != ChannelType.PUBLIC
            else None,
        )
        client = self.connect_client.get(user_id)
        if client:
            await self.send_event(
                client,
                ChatEvent(
                    event="chat.channel.part",
                    data=channel_resp.model_dump(),
                ),
            )

    async def join_room_channel(self, channel_id: int, user_id: int):
        async with AsyncSession(engine) as session:
            channel = await ChatChannel.get(channel_id, session)
            if channel is None:
                return

            user = await session.get(User, user_id)
            if user is None:
                return

            await self.join_channel(user, channel, session)

    async def leave_room_channel(self, channel_id: int, user_id: int):
        async with AsyncSession(engine) as session:
            channel = await ChatChannel.get(channel_id, session)
            if channel is None:
                return

            user = await session.get(User, user_id)
            if user is None:
                return

            await self.leave_channel(user, channel, session)


server = ChatServer()

chat_router = APIRouter(include_in_schema=False)


async def _listen_stop(ws: WebSocket, user_id: int, factory: DBFactory):
    try:
        while True:
            packets = await ws.receive_json()
            if packets.get("event") == "chat.end":
                async for session in factory():
                    user = await session.get(User, user_id)
                    if user is None:
                        break
                    await server.disconnect(user, session)
                await ws.close(code=1000)
                break
    except WebSocketDisconnect as e:
        logger.info(
            f"[NotificationServer] Client {user_id} disconnected: {e.code}, {e.reason}"
        )
    except RuntimeError as e:
        if "disconnect message" in str(e):
            logger.info(f"[NotificationServer] Client {user_id} closed the connection.")
        else:
            logger.exception(f"RuntimeError in client {user_id}: {e}")
    except Exception:
        logger.exception(f"Error in client {user_id}")


@chat_router.websocket("/notification-server")
async def chat_websocket(
    websocket: WebSocket,
    authorization: str = Header(...),
    factory: DBFactory = Depends(get_db_factory),
):
    if not server._subscribed:
        server._subscribed = True
        await server.ChatSubscriber.start_subscribe()

    async for session in factory():
        token = authorization[7:]
        if (
            user := await get_current_user(
                SecurityScopes(scopes=["chat.read"]), session, token_pw=token
            )
        ) is None:
            await websocket.close(code=1008)
            return

        await websocket.accept()
        login = await websocket.receive_json()
        if login.get("event") != "chat.start":
            await websocket.close(code=1008)
            return
        user_id = user.id
        assert user_id
        server.connect(user_id, websocket)
        channel = await ChatChannel.get(1, session)
        if channel is not None:
            await server.join_channel(user, channel, session)
    await _listen_stop(websocket, user_id, factory)
