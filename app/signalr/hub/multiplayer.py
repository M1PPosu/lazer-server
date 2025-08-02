from __future__ import annotations

from typing import override

from app.database import Room
from app.database.beatmap import Beatmap
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
from app.models.score import GameMode
from app.models.signalr import serialize_to_list

from .hub import Client, Hub

from msgpack_lazer_api import APIMod
from sqlmodel import select
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

    async def ChangeUserStyle(
        self, client: Client, beatmap_id: int | None, ruleset_id: int | None
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

        await self.change_user_style(
            beatmap_id,
            ruleset_id,
            server_room,
            user,
        )

    async def validate_styles(self, room: ServerMultiplayerRoom):
        assert room.queue
        if not room.queue.current_item.freestyle:
            for user in room.room.users:
                await self.change_user_style(
                    None,
                    None,
                    room,
                    user,
                )
        async with AsyncSession(engine) as session:
            beatmap = await session.get(Beatmap, room.queue.current_item.beatmap_id)
            if beatmap is None:
                raise InvokeException("Beatmap not found")
            beatmap_ids = (
                await session.exec(
                    select(Beatmap.id, Beatmap.mode).where(
                        Beatmap.beatmapset_id == beatmap.beatmapset_id,
                    )
                )
            ).all()
            for user in room.room.users:
                beatmap_id = user.beatmap_id
                ruleset_id = user.ruleset_id
                user_beatmap = next(
                    (b for b in beatmap_ids if b[0] == beatmap_id),
                    None,
                )
                if beatmap_id is not None and user_beatmap is None:
                    beatmap_id = None
                beatmap_ruleset = user_beatmap[1] if user_beatmap else beatmap.mode
                if (
                    ruleset_id is not None
                    and beatmap_ruleset != GameMode.OSU
                    and ruleset_id != beatmap_ruleset
                ):
                    ruleset_id = None
                await self.change_user_style(
                    beatmap_id,
                    ruleset_id,
                    room,
                    user,
                )

        for user in room.room.users:
            is_valid, valid_mods = room.queue.current_item.validate_user_mods(
                user, user.mods
            )
            if not is_valid:
                await self.change_user_mods(valid_mods, room, user)

    async def change_user_style(
        self,
        beatmap_id: int | None,
        ruleset_id: int | None,
        room: ServerMultiplayerRoom,
        user: MultiplayerRoomUser,
    ):
        if user.beatmap_id == beatmap_id and user.ruleset_id == ruleset_id:
            return

        if beatmap_id is not None or ruleset_id is not None:
            assert room.queue
            if not room.queue.current_item.freestyle:
                raise InvokeException("Current item does not allow free user styles.")

            async with AsyncSession(engine) as session:
                item_beatmap = await session.get(
                    Beatmap, room.queue.current_item.beatmap_id
                )
                if item_beatmap is None:
                    raise InvokeException("Item beatmap not found")

                user_beatmap = (
                    item_beatmap
                    if beatmap_id is None
                    else await session.get(Beatmap, beatmap_id)
                )

                if user_beatmap is None:
                    raise InvokeException("Invalid beatmap selected.")

                if user_beatmap.beatmapset_id != item_beatmap.beatmapset_id:
                    raise InvokeException(
                        "Selected beatmap is not from the same beatmap set."
                    )

                if (
                    ruleset_id is not None
                    and user_beatmap.mode != GameMode.OSU
                    and ruleset_id != user_beatmap.mode
                ):
                    raise InvokeException(
                        "Selected ruleset is not supported for the given beatmap."
                    )

        user.beatmap_id = beatmap_id
        user.ruleset_id = ruleset_id

        await self.broadcast_group_call(
            self.group_id(room.room.room_id),
            "UserStyleChanged",
            user.user_id,
            beatmap_id,
            ruleset_id,
        )

    async def ChangeUserMods(self, client: Client, new_mods: list[APIMod]):
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

        await self.change_user_mods(new_mods, server_room, user)

    async def change_user_mods(
        self,
        new_mods: list[APIMod],
        room: ServerMultiplayerRoom,
        user: MultiplayerRoomUser,
    ):
        assert room.queue
        is_valid, valid_mods = room.queue.current_item.validate_user_mods(
            user, new_mods
        )
        if not is_valid:
            incompatible_mods = [
                mod.acronym for mod in new_mods if mod not in valid_mods
            ]
            raise InvokeException(
                f"Incompatible mods were selected: {','.join(incompatible_mods)}"
            )

        if user.mods == valid_mods:
            return

        user.mods = valid_mods

        await self.broadcast_group_call(
            self.group_id(room.room.room_id),
            "UserModsChanged",
            user.user_id,
            valid_mods,
        )
