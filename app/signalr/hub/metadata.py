from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from datetime import UTC, datetime
from typing import override

from app.database import Relationship, RelationshipType, User
from app.dependencies.database import engine, get_redis
from app.models.metadata_hub import MetadataClientState, OnlineStatus, UserActivity

from .hub import Client, Hub

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

ONLINE_PRESENCE_WATCHERS_GROUP = "metadata:online-presence-watchers"


class MetadataHub(Hub[MetadataClientState]):
    def __init__(self) -> None:
        super().__init__()

    @staticmethod
    def online_presence_watchers_group() -> str:
        return ONLINE_PRESENCE_WATCHERS_GROUP

    def broadcast_tasks(
        self, user_id: int, store: MetadataClientState | None
    ) -> set[Coroutine]:
        if store is not None and not store.pushable:
            return set()
        data = store.for_push if store else None
        return {
            self.broadcast_group_call(
                self.online_presence_watchers_group(),
                "UserPresenceUpdated",
                user_id,
                data,
            ),
            self.broadcast_group_call(
                self.friend_presence_watchers_group(user_id),
                "FriendPresenceUpdated",
                user_id,
                data,
            ),
        }

    @staticmethod
    def friend_presence_watchers_group(user_id: int):
        return f"metadata:friend-presence-watchers:{user_id}"

    @override
    async def _clean_state(self, state: MetadataClientState) -> None:
        if state.pushable:
            await asyncio.gather(*self.broadcast_tasks(int(state.connection_id), None))
        redis = get_redis()
        if await redis.exists(f"metadata:online:{state.connection_id}"):
            await redis.delete(f"metadata:online:{state.connection_id}")
        async with AsyncSession(engine) as session:
            async with session.begin():
                user = (
                    await session.exec(
                        select(User).where(User.id == int(state.connection_id))
                    )
                ).one()
                user.last_visit = datetime.now(UTC)
                await session.commit()

    @override
    def create_state(self, client: Client) -> MetadataClientState:
        return MetadataClientState(
            connection_id=client.connection_id,
            connection_token=client.connection_token,
        )

    async def on_client_connect(self, client: Client) -> None:
        user_id = int(client.connection_id)
        self.get_or_create_state(client)

        async with AsyncSession(engine) as session:
            async with session.begin():
                friends = (
                    await session.exec(
                        select(Relationship.target_id).where(
                            Relationship.user_id == user_id,
                            Relationship.type == RelationshipType.FOLLOW,
                        )
                    )
                ).all()
                tasks = []
                for friend_id in friends:
                    self.groups.setdefault(
                        self.friend_presence_watchers_group(friend_id), set()
                    ).add(client)
                    if (
                        friend_state := self.state.get(friend_id)
                    ) and friend_state.pushable:
                        tasks.append(
                            self.broadcast_group_call(
                                self.friend_presence_watchers_group(friend_id),
                                "FriendPresenceUpdated",
                                friend_id,
                                friend_state.for_push
                                if friend_state.pushable
                                else None,
                            )
                        )
                await asyncio.gather(*tasks)
        redis = get_redis()
        await redis.set(f"metadata:online:{user_id}", "")

    async def UpdateStatus(self, client: Client, status: int) -> None:
        status_ = OnlineStatus(status)
        user_id = int(client.connection_id)
        store = self.get_or_create_state(client)
        if store.status is not None and store.status == status_:
            return
        store.status = OnlineStatus(status_)
        tasks = self.broadcast_tasks(user_id, store)
        tasks.add(
            self.call_noblock(
                client,
                "UserPresenceUpdated",
                user_id,
                store.for_push,
            )
        )
        await asyncio.gather(*tasks)

    async def UpdateActivity(
        self, client: Client, activity: UserActivity | None
    ) -> None:
        user_id = int(client.connection_id)
        store = self.get_or_create_state(client)
        store.activity = activity
        tasks = self.broadcast_tasks(user_id, store)
        tasks.add(
            self.call_noblock(
                client,
                "UserPresenceUpdated",
                user_id,
                store.for_push,
            )
        )
        await asyncio.gather(*tasks)

    async def BeginWatchingUserPresence(self, client: Client) -> None:
        await asyncio.gather(
            *[
                self.call_noblock(
                    client,
                    "UserPresenceUpdated",
                    user_id,
                    store,
                )
                for user_id, store in self.state.items()
                if store.pushable
            ]
        )
        self.add_to_group(client, self.online_presence_watchers_group())

    async def EndWatchingUserPresence(self, client: Client) -> None:
        self.remove_from_group(client, self.online_presence_watchers_group())
