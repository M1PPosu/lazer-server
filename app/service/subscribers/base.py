from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from fnmatch import fnmatch
from typing import Any

from app.dependencies.database import get_redis_pubsub


class RedisSubscriber:
    def __init__(self):
        self.pubsub = get_redis_pubsub()
        self.handlers: dict[str, list[Callable[[str, str], Awaitable[Any]]]] = {}
        self.task: asyncio.Task | None = None

    async def subscribe(self, channel: str):
        await self.pubsub.subscribe(channel)
        if channel not in self.handlers:
            self.handlers[channel] = []

    async def unsubscribe(self, channel: str):
        if channel in self.handlers:
            del self.handlers[channel]
        await self.pubsub.unsubscribe(channel)

    async def listen(self):
        while True:
            message = await self.pubsub.get_message(
                ignore_subscribe_messages=True, timeout=None
            )
            if message is not None and message["type"] == "message":
                matched_handlers = []
                if message["channel"] in self.handlers:
                    matched_handlers.extend(self.handlers[message["channel"]])
                for pattern, handlers in self.handlers.items():
                    if fnmatch(message["channel"], pattern):
                        matched_handlers.extend(handlers)
                if matched_handlers:
                    await asyncio.gather(
                        *[
                            handler(message["channel"], message["data"])
                            for handler in matched_handlers
                        ]
                    )

    def start(self):
        if self.task is None or self.task.done():
            self.task = asyncio.create_task(self.listen())

    def stop(self):
        if self.task is not None and not self.task.done():
            self.task.cancel()
            self.task = None
