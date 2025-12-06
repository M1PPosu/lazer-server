from app.dependencies.database import get_redis
from app.log import logger
from app.service.user_cache_service import get_user_cache_service

from .base import RedisSubscriber

KEY = "user:online_status"


class UserOnlineSubscriber(RedisSubscriber):
    async def start_subscribe(self):
        await self.subscribe(KEY)
        self.add_handler(KEY, self.on)
        self.start()

    async def on(self, c: str, s: str):  # noqa: ARG002
        user_id = int(s)
        logger.info(f"Received user online status update for user_id: {s}")
        await get_user_cache_service(get_redis()).invalidate_user_cache(user_id)


user_online_subscriber = UserOnlineSubscriber()
