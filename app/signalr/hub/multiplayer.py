from __future__ import annotations

from typing import override

from app.database import Room
from app.database.playlists import Playlist
from app.dependencies.database import engine
from app.exception import InvokeException
from app.log import logger
from app.models.multiplayer_hub import (
    BeatmapAvailability,
    MultiplayerClientState,
    MultiplayerQueue,
    MultiplayerRoom,
    MultiplayerRoomUser,
    PlaylistItem,
    ServerMultiplayerRoom,
)
from app.models.room import RoomCategory, RoomStatus
from app.models.signalr import serialize_to_list

from .hub import Client, Hub

from sqlmodel.ext.asyncio.session import AsyncSession


class MultiplayerHub(Hub[MultiplayerClientState]):
    @override
    def __init__(self):
        super().__init__()
        self.rooms: dict[int, ServerMultiplayerRoom] = {}

    @staticmethod
    def group_id(room: int) -> str:
        return f"room:{room}"

    @override
    def create_state(self, client: Client) -> MultiplayerClientState:
        return MultiplayerClientState(
            connection_id=client.connection_id,
            connection_token=client.connection_token,
        )

    async def CreateRoom(self, client: Client, room: MultiplayerRoom):
        logger.info(f"[MultiplayerHub] {client.user_id} creating room")
        store = self.get_or_create_state(client)
        if store.room_id != 0:
            raise InvokeException("You are already in a room")
        async with AsyncSession(engine) as session:
            async with session:
                db_room = Room(
                    name=room.settings.name,
                    category=RoomCategory.NORMAL,
                    type=room.settings.match_type,
                    queue_mode=room.settings.queue_mode,
                    auto_skip=room.settings.auto_skip,
                    auto_start_duration=room.settings.auto_start_duration,
                    host_id=client.user_id,
                    status=RoomStatus.IDLE,
                )
                session.add(db_room)
                await session.commit()
                await session.refresh(db_room)
                item = room.playlist[0]
                item.owner_id = client.user_id
                room.room_id = db_room.id
                starts_at = db_room.starts_at
                await Playlist.add_to_db(item, db_room.id, session)
                server_room = ServerMultiplayerRoom(
                    room=room,
                    category=RoomCategory.NORMAL,
                    status=RoomStatus.IDLE,
                    start_at=starts_at,
                )
                queue = MultiplayerQueue(
                    room=server_room,
                    hub=self,
                )
                server_room.queue = queue
                self.rooms[room.room_id] = server_room
                return await self.JoinRoomWithPassword(
                    client, room.room_id, room.settings.password
                )

    async def JoinRoomWithPassword(self, client: Client, room_id: int, password: str):
        logger.info(f"[MultiplayerHub] {client.user_id} joining room {room_id}")
        store = self.get_or_create_state(client)
        if store.room_id != 0:
            raise InvokeException("You are already in a room")
        user = MultiplayerRoomUser(user_id=client.user_id)
        if room_id not in self.rooms:
            raise InvokeException("Room does not exist")
        server_room = self.rooms[room_id]
        room = server_room.room
        for u in room.users:
            if u.user_id == client.user_id:
                raise InvokeException("You are already in this room")
        if room.settings.password != password:
            raise InvokeException("Incorrect password")
        if room.host is None:
            # from CreateRoom
            room.host = user
        store.room_id = room_id
        await self.broadcast_group_call(
            self.group_id(room_id), "UserJoined", serialize_to_list(user)
        )
        room.users.append(user)
        self.add_to_group(client, self.group_id(room_id))
        return serialize_to_list(room)

    async def ChangeBeatmapAvailability(
        self, client: Client, beatmap_availability: BeatmapAvailability
    ):
        store = self.get_or_create_state(client)
        if store.room_id == 0:
            raise InvokeException("You are not in a room")
        if store.room_id not in self.rooms:
            raise InvokeException("Room does not exist")
        server_room = self.rooms[store.room_id]
        room = server_room.room
        user = next((u for u in room.users if u.user_id == client.user_id), None)
        if user is None:
            raise InvokeException("You are not in this room")

        availability = user.availability
        if (
            availability.state == beatmap_availability.state
            and availability.progress == beatmap_availability.progress
        ):
            return
        user.availability = availability
        await self.broadcast_group_call(
            self.group_id(store.room_id),
            "UserBeatmapAvailabilityChanged",
            user.user_id,
            serialize_to_list(beatmap_availability),
        )

    async def AddPlaylistItem(self, client: Client, item: PlaylistItem):
        store = self.get_or_create_state(client)
        if store.room_id == 0:
            raise InvokeException("You are not in a room")
        if store.room_id not in self.rooms:
            raise InvokeException("Room does not exist")
        server_room = self.rooms[store.room_id]
        room = server_room.room
        assert server_room.queue
        user = next((u for u in room.users if u.user_id == client.user_id), None)
        if user is None:
            raise InvokeException("You are not in this room")

        await server_room.queue.add_item(
            item,
            user,
        )

    async def EditPlaylistItem(self, client: Client, item: PlaylistItem):
        store = self.get_or_create_state(client)
        if store.room_id == 0:
            raise InvokeException("You are not in a room")
        if store.room_id not in self.rooms:
            raise InvokeException("Room does not exist")
        server_room = self.rooms[store.room_id]
        room = server_room.room
        assert server_room.queue
        user = next((u for u in room.users if u.user_id == client.user_id), None)
        if user is None:
            raise InvokeException("You are not in this room")

        await server_room.queue.edit_item(
            item,
            user,
        )

    async def RemovePlaylistItem(self, client: Client, item_id: int):
        store = self.get_or_create_state(client)
        if store.room_id == 0:
            raise InvokeException("You are not in a room")
        if store.room_id not in self.rooms:
            raise InvokeException("Room does not exist")
        server_room = self.rooms[store.room_id]
        room = server_room.room
        assert server_room.queue
        user = next((u for u in room.users if u.user_id == client.user_id), None)
        if user is None:
            raise InvokeException("You are not in this room")

        await server_room.queue.remove_item(
            item_id,
            user,
        )

    async def setting_changed(self, room: ServerMultiplayerRoom, beatmap_changed: bool):
        await self.broadcast_group_call(
            self.group_id(room.room.room_id),
            "SettingsChanged",
            serialize_to_list(room.room.settings),
        )

    async def playlist_added(self, room: ServerMultiplayerRoom, item: PlaylistItem):
        await self.broadcast_group_call(
            self.group_id(room.room.room_id),
            "PlaylistItemAdded",
            serialize_to_list(item),
        )

    async def playlist_removed(self, room: ServerMultiplayerRoom, item_id: int):
        await self.broadcast_group_call(
            self.group_id(room.room.room_id),
            "PlaylistItemRemoved",
            item_id,
        )

    async def playlist_changed(
        self, room: ServerMultiplayerRoom, item: PlaylistItem, beatmap_changed: bool
    ):
        await self.broadcast_group_call(
            self.group_id(room.room.room_id),
            "PlaylistItemChanged",
            serialize_to_list(item),
        )
