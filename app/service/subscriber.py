from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from app.dependencies.database import get_redis_pubsub


class RedisSubscriber:
    def __init__(self, channel: str):
        self.pubsub = get_redis_pubsub(channel)
        self.handlers: dict[str, list[Callable[[str, str], Awaitable[Any]]]] = {}

    async def listen(self):
        async for message in self.pubsub.listen():
            if message is not None and message["type"] == "message":
                method = self.handlers.get(message["channel"])
                if method:
                    for handler in method:
                        await handler(message["channel"], message["data"])
