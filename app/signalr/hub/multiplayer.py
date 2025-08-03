from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import override

from app.database import Room
from app.database.beatmap import Beatmap
from app.database.playlists import Playlist
from app.dependencies.database import engine
from app.exception import InvokeException
from app.log import logger
from app.models.mods import APIMod
from app.models.multiplayer_hub import (
    BeatmapAvailability,
    ForceGameplayStartCountdown,
    GameplayAbortReason,
    MatchServerEvent,
    MultiplayerClientState,
    MultiplayerQueue,
    MultiplayerRoom,
    MultiplayerRoomUser,
    PlaylistItem,
    ServerMultiplayerRoom,
)
from app.models.room import (
    DownloadState,
    MultiplayerRoomState,
    MultiplayerUserState,
    RoomCategory,
    RoomStatus,
)
from app.models.score import GameMode

from .hub import Client, Hub

from sqlalchemy import update
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

GAMEPLAY_LOAD_TIMEOUT = 30


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
                    auto_start_duration=int(
                        room.settings.auto_start_duration.total_seconds()
                    ),
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
                    hub=self,
                )
                queue = MultiplayerQueue(
                    room=server_room,
                )
                server_room.queue = queue
                self.rooms[room.room_id] = server_room
                return await self.JoinRoomWithPassword(
                    client, room.room_id, room.settings.password
                )

    async def JoinRoom(self, client: Client, room_id: int):
        return self.JoinRoomWithPassword(client, room_id, "")

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
        await self.broadcast_group_call(self.group_id(room_id), "UserJoined", user)
        room.users.append(user)
        self.add_to_group(client, self.group_id(room_id))
        return room

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
        user.availability = beatmap_availability
        await self.broadcast_group_call(
            self.group_id(store.room_id),
            "UserBeatmapAvailabilityChanged",
            user.user_id,
            (beatmap_availability),
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
            (room.room.settings),
        )

    async def playlist_added(self, room: ServerMultiplayerRoom, item: PlaylistItem):
        await self.broadcast_group_call(
            self.group_id(room.room.room_id),
            "PlaylistItemAdded",
            (item),
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
            (item),
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
                mod["acronym"] for mod in new_mods if mod not in valid_mods
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

    async def validate_user_stare(
        self,
        room: ServerMultiplayerRoom,
        old: MultiplayerUserState,
        new: MultiplayerUserState,
    ):
        assert room.queue
        match new:
            case MultiplayerUserState.IDLE:
                if old.is_playing:
                    raise InvokeException(
                        "Cannot return to idle without aborting gameplay."
                    )
            case MultiplayerUserState.READY:
                if old != MultiplayerUserState.IDLE:
                    raise InvokeException(f"Cannot change state from {old} to {new}")
                if room.queue.current_item.expired:
                    raise InvokeException(
                        "Cannot ready up while all items have been played."
                    )
            case MultiplayerUserState.WAITING_FOR_LOAD:
                raise InvokeException("Cannot change state from {old} to {new}")
            case MultiplayerUserState.LOADED:
                if old != MultiplayerUserState.WAITING_FOR_LOAD:
                    raise InvokeException(f"Cannot change state from {old} to {new}")
            case MultiplayerUserState.READY_FOR_GAMEPLAY:
                if old != MultiplayerUserState.LOADED:
                    raise InvokeException(f"Cannot change state from {old} to {new}")
            case MultiplayerUserState.PLAYING:
                raise InvokeException("State is managed by the server.")
            case MultiplayerUserState.FINISHED_PLAY:
                if old != MultiplayerUserState.PLAYING:
                    raise InvokeException(f"Cannot change state from {old} to {new}")
            case MultiplayerUserState.RESULTS:
                raise InvokeException("Cannot change state from {old} to {new}")
            case MultiplayerUserState.SPECTATING:
                if old not in (MultiplayerUserState.IDLE, MultiplayerUserState.READY):
                    raise InvokeException(f"Cannot change state from {old} to {new}")

    async def ChangeState(self, client: Client, state: MultiplayerUserState):
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

        if user.state == state:
            return
        match state:
            case MultiplayerUserState.IDLE:
                if user.state.is_playing:
                    return
            case MultiplayerUserState.LOADED | MultiplayerUserState.READY_FOR_GAMEPLAY:
                if not user.state.is_playing:
                    return
        await self.validate_user_stare(
            server_room,
            user.state,
            state,
        )
        await self.change_user_state(server_room, user, state)
        if state == MultiplayerUserState.SPECTATING and (
            room.state == MultiplayerRoomState.PLAYING
            or room.state == MultiplayerRoomState.WAITING_FOR_LOAD
        ):
            await self.call_noblock(client, "LoadRequested")
        await self.update_room_state(server_room)

    async def change_user_state(
        self,
        room: ServerMultiplayerRoom,
        user: MultiplayerRoomUser,
        state: MultiplayerUserState,
    ):
        user.state = state
        await self.broadcast_group_call(
            self.group_id(room.room.room_id),
            "UserStateChanged",
            user.user_id,
            user.state,
        )

    async def update_room_state(self, room: ServerMultiplayerRoom):
        match room.room.state:
            case MultiplayerRoomState.WAITING_FOR_LOAD:
                played_count = len(
                    [True for user in room.room.users if user.state.is_playing]
                )
                ready_count = len(
                    [
                        True
                        for user in room.room.users
                        if user.state == MultiplayerUserState.READY_FOR_GAMEPLAY
                    ]
                )
                if played_count == ready_count:
                    await self.start_gameplay(room)
            case MultiplayerRoomState.PLAYING:
                assert room.queue
                if all(
                    u.state != MultiplayerUserState.PLAYING for u in room.room.users
                ):
                    for u in filter(
                        lambda u: u.state == MultiplayerUserState.FINISHED_PLAY,
                        room.room.users,
                    ):
                        await self.change_user_state(
                            room, u, MultiplayerUserState.RESULTS
                        )
                    await self.change_room_state(room, MultiplayerRoomState.OPEN)
                    await self.broadcast_group_call(
                        self.group_id(room.room.room_id),
                        "ResultsReady",
                    )
                    await room.queue.finish_current_item()

    async def change_room_state(
        self, room: ServerMultiplayerRoom, state: MultiplayerRoomState
    ):
        room.room.state = state
        await self.broadcast_group_call(
            self.group_id(room.room.room_id),
            "RoomStateChanged",
            state,
        )

    async def StartMatch(self, client: Client):
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
        if room.host is None or room.host.user_id != client.user_id:
            raise InvokeException("You are not the host of this room")
        if any(u.state != MultiplayerUserState.READY for u in room.users):
            raise InvokeException("Not all users are ready")

        await self.start_match(server_room)

    async def start_match(self, room: ServerMultiplayerRoom):
        assert room.queue
        if room.room.state != MultiplayerRoomState.OPEN:
            raise InvokeException("Can't start match when already in a running state.")
        if room.queue.current_item.expired:
            raise InvokeException("Current playlist item is expired")
        ready_users = [
            u
            for u in room.room.users
            if u.availability.state == DownloadState.LOCALLY_AVAILABLE
            and (
                u.state == MultiplayerUserState.READY
                or u.state == MultiplayerUserState.IDLE
            )
        ]
        await asyncio.gather(
            *[
                self.change_user_state(room, u, MultiplayerUserState.WAITING_FOR_LOAD)
                for u in ready_users
            ]
        )
        await self.change_room_state(
            room,
            MultiplayerRoomState.WAITING_FOR_LOAD,
        )
        await self.broadcast_group_call(
            self.group_id(room.room.room_id),
            "LoadRequested",
        )
        await room.start_countdown(
            ForceGameplayStartCountdown(
                remaining=timedelta(seconds=GAMEPLAY_LOAD_TIMEOUT)
            ),
            self.start_gameplay,
        )

    async def start_gameplay(self, room: ServerMultiplayerRoom):
        assert room.queue
        if room.room.state != MultiplayerRoomState.WAITING_FOR_LOAD:
            raise InvokeException("Room is not ready for gameplay")
        if room.queue.current_item.expired:
            raise InvokeException("Current playlist item is expired")
        playing = False
        for user in room.room.users:
            client = self.get_client_by_id(str(user.user_id))
            if client is None:
                continue

            if user.state in (
                MultiplayerUserState.READY_FOR_GAMEPLAY,
                MultiplayerUserState.LOADED,
            ):
                playing = True
                await self.change_user_state(room, user, MultiplayerUserState.PLAYING)
                await self.call_noblock(client, "GameplayStarted")
            elif user.state == MultiplayerUserState.WAITING_FOR_LOAD:
                await self.change_user_state(room, user, MultiplayerUserState.IDLE)
                await self.broadcast_group_call(
                    self.group_id(room.room.room_id),
                    "GameplayAborted",
                    GameplayAbortReason.LOAD_TOOK_TOO_LONG,
                )
        await self.change_room_state(
            room,
            (MultiplayerRoomState.PLAYING if playing else MultiplayerRoomState.OPEN),
        )

    async def send_match_event(
        self, room: ServerMultiplayerRoom, event: MatchServerEvent
    ):
        await self.broadcast_group_call(
            self.group_id(room.room.room_id),
            "MatchEvent",
            event,
        )

    async def make_user_leave(
        self,
        client: Client,
        room: ServerMultiplayerRoom,
        user: MultiplayerRoomUser,
        kicked: bool = False,
    ):
        self.remove_from_group(client, self.group_id(room.room.room_id))
        room.room.users.remove(user)

        if len(room.room.users) == 0:
            await self.end_room(room)
        await self.update_room_state(room)
        if room.room.host and room.room.host.user_id == user.user_id:
            next_host = room.room.users[0]
            await self.set_host(room, next_host)

        if kicked:
            await self.call_noblock(client, "UserKicked", user)
            await self.broadcast_group_call(
                self.group_id(room.room.room_id), "UserKicked", user
            )
        else:
            await self.broadcast_group_call(
                self.group_id(room.room.room_id), "UserLeft", user
            )

        target_store = self.state.get(user.user_id)
        if target_store:
            target_store.room_id = 0

    async def end_room(self, room: ServerMultiplayerRoom):
        assert room.room.host
        async with AsyncSession(engine) as session:
            await session.execute(
                update(Room)
                .where(col(Room.id) == room.room.room_id)
                .values(
                    name=room.room.settings.name,
                    ended_at=datetime.now(UTC),
                    type=room.room.settings.match_type,
                    queue_mode=room.room.settings.queue_mode,
                    auto_skip=room.room.settings.auto_skip,
                    auto_start_duration=int(
                        room.room.settings.auto_start_duration.total_seconds()
                    ),
                    host_id=room.room.host.user_id,
                )
            )
        del self.rooms[room.room.room_id]

    async def LeaveRoom(self, client: Client):
        store = self.get_or_create_state(client)
        if store.room_id == 0:
            return
        if store.room_id not in self.rooms:
            raise InvokeException("Room does not exist")
        server_room = self.rooms[store.room_id]
        room = server_room.room
        user = next((u for u in room.users if u.user_id == client.user_id), None)
        if user is None:
            raise InvokeException("You are not in this room")

        await self.make_user_leave(client, server_room, user)

    async def KickUser(self, client: Client, user_id: int):
        store = self.get_or_create_state(client)
        if store.room_id == 0:
            raise InvokeException("You are not in a room")
        if store.room_id not in self.rooms:
            raise InvokeException("Room does not exist")
        server_room = self.rooms[store.room_id]
        room = server_room.room

        if room.host is None or room.host.user_id != client.user_id:
            raise InvokeException("You are not the host of this room")

        user = next((u for u in room.users if u.user_id == user_id), None)
        if user is None:
            raise InvokeException("User not found in this room")

        target_client = self.get_client_by_id(str(user.user_id))
        if target_client is None:
            return
        await self.make_user_leave(target_client, server_room, user, kicked=True)

    async def set_host(self, room: ServerMultiplayerRoom, user: MultiplayerRoomUser):
        room.room.host = user
        await self.broadcast_group_call(
            self.group_id(room.room.room_id),
            "HostChanged",
            user.user_id,
        )

    async def TransferHost(self, client: Client, user_id: int):
        store = self.get_or_create_state(client)
        if store.room_id == 0:
            raise InvokeException("You are not in a room")
        if store.room_id not in self.rooms:
            raise InvokeException("Room does not exist")
        server_room = self.rooms[store.room_id]
        room = server_room.room

        if room.host is None or room.host.user_id != client.user_id:
            raise InvokeException("You are not the host of this room")

        new_host = next((u for u in room.users if u.user_id == user_id), None)
        if new_host is None:
            raise InvokeException("User not found in this room")
        await self.set_host(server_room, new_host)

    async def AbortGameplay(self, client: Client):
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

        if not user.state.is_playing:
            raise InvokeException("Cannot abort gameplay while not in a gameplay state")

        await self.change_user_state(
            server_room,
            user,
            MultiplayerUserState.IDLE,
        )
        await self.update_room_state(server_room)

    async def AbortMatch(self, client: Client):
        store = self.get_or_create_state(client)
        if store.room_id == 0:
            raise InvokeException("You are not in a room")
        if store.room_id not in self.rooms:
            raise InvokeException("Room does not exist")
        server_room = self.rooms[store.room_id]
        room = server_room.room

        if room.host is None or room.host.user_id != client.user_id:
            raise InvokeException("You are not the host of this room")

        if (
            room.state != MultiplayerRoomState.PLAYING
            or room.state == MultiplayerRoomState.WAITING_FOR_LOAD
        ):
            raise InvokeException("Room is not in a playable state")

        await asyncio.gather(
            *[
                self.change_user_state(server_room, u, MultiplayerUserState.IDLE)
                for u in room.users
                if u.state.is_playing
            ]
        )
        await self.broadcast_group_call(
            self.group_id(room.room_id),
            "GameplayAborted",
            GameplayAbortReason.HOST_ABORTED,
        )
        await self.update_room_state(server_room)
