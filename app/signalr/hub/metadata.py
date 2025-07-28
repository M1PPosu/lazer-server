from __future__ import annotations

import asyncio
from collections.abc import Coroutine

from app.database.relationship import Relationship, RelationshipType
from app.dependencies.database import engine
from app.models.metadata_hub import MetadataClientState, OnlineStatus, UserActivity

from .hub import Client, Hub

from pydantic import TypeAdapter
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

ONLINE_PRESENCE_WATCHERS_GROUP = "metadata:online-presence-watchers"


class MetadataHub(Hub):
    def __init__(self) -> None:
        super().__init__()
        self.state: dict[int, MetadataClientState] = {}

    @staticmethod
    def online_presence_watchers_group() -> str:
        return ONLINE_PRESENCE_WATCHERS_GROUP

    def broadcast_tasks(
        self, user_id: int, store: MetadataClientState
    ) -> set[Coroutine]:
        if not store.pushable:
            return set()
        return {
            self.broadcast_group_call(
                self.online_presence_watchers_group(),
                "UserPresenceUpdated",
                user_id,
                store.to_dict(),
            ),
            self.broadcast_group_call(
                self.friend_presence_watchers_group(user_id),
                "FriendPresenceUpdated",
                user_id,
                store.to_dict(),
            ),
        }

    @staticmethod
    def friend_presence_watchers_group(user_id: int):
        return f"metadata:friend-presence-watchers:{user_id}"

    async def on_client_connect(self, client: Client) -> None:
        user_id = int(client.connection_id)
        if store := self.state.get(user_id):
            store = MetadataClientState()
            self.state[user_id] = store

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
                                friend_state.to_dict(),
                            )
                        )
                await asyncio.gather(*tasks)

    async def UpdateStatus(self, client: Client, status: int) -> None:
        status_ = OnlineStatus(status)
        user_id = int(client.connection_id)
        store = self.state.get(user_id)
        if store:
            if store.status is not None and store.status == status_:
                return
            store.status = OnlineStatus(status_)
        else:
            store = MetadataClientState(status=OnlineStatus(status_))
            self.state[user_id] = store
        tasks = self.broadcast_tasks(user_id, store)
        tasks.add(
            self.call_noblock(
                client,
                "UserPresenceUpdated",
                user_id,
                store.to_dict(),
            )
        )
        await asyncio.gather(*tasks)

    async def UpdateActivity(self, client: Client, activity_dict: dict | None) -> None:
        user_id = int(client.connection_id)
        activity = (
            TypeAdapter(UserActivity).validate_python(activity_dict)
            if activity_dict
            else None
        )
        store = self.state.get(user_id)
        if store:
            store.user_activity = activity
        else:
            store = MetadataClientState(
                user_activity=activity,
            )
            self.state[user_id] = store
        tasks = self.broadcast_tasks(user_id, store)
        tasks.add(
            self.call_noblock(
                client,
                "UserPresenceUpdated",
                user_id,
                store.to_dict(),
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
                    store.to_dict(),
                )
                for user_id, store in self.state.items()
                if store.pushable
            ]
        )
        self.groups.setdefault(self.online_presence_watchers_group(), set()).add(client)

    async def EndWatchingUserPresence(self, client: Client) -> None:
        self.groups.setdefault(self.online_presence_watchers_group(), set()).discard(
            client
        )
