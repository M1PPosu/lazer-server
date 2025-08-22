from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import override, Dict, List, Optional, Tuple
import json
from collections import defaultdict, deque

from app.database import Room
from app.database.beatmap import Beatmap
from app.database.chat import ChannelType, ChatChannel
from app.database.lazer_user import User
from app.database.multiplayer_event import MultiplayerEvent
from app.database.playlists import Playlist
from app.database.relationship import Relationship, RelationshipType
from app.database.room_participated_user import RoomParticipatedUser
from app.dependencies.database import get_redis, with_db
from app.dependencies.fetcher import get_fetcher
from app.exception import InvokeException
from app.log import logger
from app.models.mods import APIMod
from app.models.multiplayer_hub import (
    BeatmapAvailability,
    ForceGameplayStartCountdown,
    GameplayAbortReason,
    MatchRequest,
    MatchServerEvent,
    MatchStartCountdown,
    MatchStartedEventDetail,
    MultiplayerClientState,
    MultiplayerRoom,
    MultiplayerRoomSettings,
    MultiplayerRoomUser,
    PlaylistItem,
    ServerMultiplayerRoom,
    ServerShuttingDownCountdown,
    StartMatchCountdownRequest,
    StopCountdownRequest,
)
from app.models.room import (
    DownloadState,
    MatchType,
    MultiplayerRoomState,
    MultiplayerUserState,
    RoomCategory,
    RoomStatus,
)
from app.models.score import GameMode

from .hub import Client, Hub

from httpx import HTTPError
from sqlalchemy import update
from sqlmodel import col, exists, select

GAMEPLAY_LOAD_TIMEOUT = 30


class GameplayStateBuffer:
    """游戏状态缓冲区，用于管理实时排行榜和观战数据同步"""
    
    def __init__(self):
        # 房间ID -> 用户分数数据缓冲区
        self.score_buffers: Dict[int, Dict[int, deque]] = defaultdict(lambda: defaultdict(lambda: deque(maxlen=50)))
        # 房间ID -> 实时排行榜数据
        self.leaderboards: Dict[int, List[Dict]] = defaultdict(list)
        # 房间ID -> 游戏状态快照
        self.gameplay_snapshots: Dict[int, Dict] = {}
        # 用户观战状态缓存
        self.spectator_states: Dict[Tuple[int, int], Dict] = {}  # (room_id, user_id) -> state
        
    async def add_score_frame(self, room_id: int, user_id: int, frame_data: Dict):
        """添加分数帧数据到缓冲区"""
        self.score_buffers[room_id][user_id].append({
            **frame_data,
            'timestamp': datetime.now(UTC),
            'user_id': user_id
        })
        
        # 更新实时排行榜
        await self._update_leaderboard(room_id)
    
    async def _update_leaderboard(self, room_id: int):
        """更新实时排行榜"""
        leaderboard = []
        
        for user_id, frames in self.score_buffers[room_id].items():
            if not frames:
                continue
                
            latest_frame = frames[-1]
            leaderboard.append({
                'user_id': user_id,
                'score': latest_frame.get('score', 0),
                'combo': latest_frame.get('combo', 0),
                'accuracy': latest_frame.get('accuracy', 0.0),
                'completed': latest_frame.get('completed', False),
                'timestamp': latest_frame['timestamp']
            })
        
        # 按分数排序
        leaderboard.sort(key=lambda x: (-x['score'], -x['accuracy']))
        self.leaderboards[room_id] = leaderboard
    
    def get_leaderboard(self, room_id: int) -> List[Dict]:
        """获取房间实时排行榜"""
        return self.leaderboards.get(room_id, [])
    
    async def create_gameplay_snapshot(self, room_id: int, room_data: Dict):
        """创建游戏状态快照用于新加入的观众"""
        snapshot = {
            'room_id': room_id,
            'state': room_data.get('state'),
            'current_item': room_data.get('current_item'),
            'users': room_data.get('users', []),
            'leaderboard': self.get_leaderboard(room_id),
            'created_at': datetime.now(UTC)
        }
        self.gameplay_snapshots[room_id] = snapshot
        return snapshot
    
    def get_gameplay_snapshot(self, room_id: int) -> Optional[Dict]:
        """获取游戏状态快照"""
        return self.gameplay_snapshots.get(room_id)
    
    async def set_spectator_state(self, room_id: int, user_id: int, state_data: Dict):
        """设置观战者状态"""
        key = (room_id, user_id)
        self.spectator_states[key] = {
            **state_data,
            'last_updated': datetime.now(UTC)
        }
    
    def get_spectator_state(self, room_id: int, user_id: int) -> Optional[Dict]:
        """获取观战者状态"""
        key = (room_id, user_id)
        return self.spectator_states.get(key)
    
    async def cleanup_room(self, room_id: int):
        """清理房间相关数据"""
        self.score_buffers.pop(room_id, None)
        self.leaderboards.pop(room_id, None)
        self.gameplay_snapshots.pop(room_id, None)
        
        # 清理观战者状态
        keys_to_remove = [key for key in self.spectator_states.keys() if key[0] == room_id]
        for key in keys_to_remove:
            self.spectator_states.pop(key, None)


class SpectatorSyncManager:
    """观战同步管理器，处理跨Hub通信"""
    
    def __init__(self, redis_client):
        self.redis = redis_client
        self.channel_prefix = "multiplayer_spectator"
    
    async def notify_spectator_hubs(self, room_id: int, event_type: str, data: Dict):
        """通知观战Hub游戏状态变化"""
        message = {
            'room_id': room_id,
            'event_type': event_type,
            'data': data,
            'timestamp': datetime.now(UTC).isoformat()
        }
        
        channel = f"{self.channel_prefix}:room:{room_id}"
        await self.redis.publish(channel, json.dumps(message))
    
    async def notify_gameplay_started(self, room_id: int, game_data: Dict):
        """通知游戏开始"""
        await self.notify_spectator_hubs(room_id, "gameplay_started", game_data)
    
    async def notify_gameplay_ended(self, room_id: int, results_data: Dict):
        """通知游戏结束"""
        await self.notify_spectator_hubs(room_id, "gameplay_ended", results_data)
    
    async def notify_user_state_change(self, room_id: int, user_id: int, old_state: str, new_state: str):
        """通知用户状态变化"""
        await self.notify_spectator_hubs(room_id, "user_state_changed", {
            'user_id': user_id,
            'old_state': old_state,
            'new_state': new_state
        })
    
    async def subscribe_to_spectator_events(self, callback):
        """订阅观战事件"""
        pattern = f"{self.channel_prefix}:*"
        pubsub = self.redis.pubsub()
        await pubsub.psubscribe(pattern)
        
        async for message in pubsub.listen():
            if message['type'] == 'pmessage':
                try:
                    data = json.loads(message['data'])
                    await callback(message['channel'], data)
                except Exception as e:
                    logger.error(f"Error processing spectator event: {e}")


# 全局实例
gameplay_buffer = GameplayStateBuffer()


class MultiplayerEventLogger:
    def __init__(self):
        pass

    async def log_event(self, event: MultiplayerEvent):
        try:
            async with with_db() as session:
                session.add(event)
                await session.commit()
        except Exception as e:
            logger.warning(f"Failed to log multiplayer room event to database: {e}")

    async def room_created(self, room_id: int, user_id: int):
        event = MultiplayerEvent(
            room_id=room_id,
            user_id=user_id,
            event_type="room_created",
        )
        await self.log_event(event)

    async def room_disbanded(self, room_id: int, user_id: int):
        event = MultiplayerEvent(
            room_id=room_id,
            user_id=user_id,
            event_type="room_disbanded",
        )
        await self.log_event(event)

    async def player_joined(self, room_id: int, user_id: int):
        event = MultiplayerEvent(
            room_id=room_id,
            user_id=user_id,
            event_type="player_joined",
        )
        await self.log_event(event)

    async def player_left(self, room_id: int, user_id: int):
        event = MultiplayerEvent(
            room_id=room_id,
            user_id=user_id,
            event_type="player_left",
        )
        await self.log_event(event)

    async def player_kicked(self, room_id: int, user_id: int):
        event = MultiplayerEvent(
            room_id=room_id,
            user_id=user_id,
            event_type="player_kicked",
        )
        await self.log_event(event)

    async def host_changed(self, room_id: int, user_id: int):
        event = MultiplayerEvent(
            room_id=room_id,
            user_id=user_id,
            event_type="host_changed",
        )
        await self.log_event(event)

    async def game_started(
        self, room_id: int, playlist_item_id: int, details: MatchStartedEventDetail
    ):
        event = MultiplayerEvent(
            room_id=room_id,
            playlist_item_id=playlist_item_id,
            event_type="game_started",
            event_detail=details,  # pyright: ignore[reportArgumentType]
        )
        await self.log_event(event)

    async def game_aborted(self, room_id: int, playlist_item_id: int):
        event = MultiplayerEvent(
            room_id=room_id,
            playlist_item_id=playlist_item_id,
            event_type="game_aborted",
        )
        await self.log_event(event)

    async def game_completed(self, room_id: int, playlist_item_id: int):
        event = MultiplayerEvent(
            room_id=room_id,
            playlist_item_id=playlist_item_id,
            event_type="game_completed",
        )
        await self.log_event(event)


class MultiplayerHub(Hub[MultiplayerClientState]):
    @override
    def __init__(self):
        super().__init__()
        self.rooms: dict[int, ServerMultiplayerRoom] = {}
        self.event_logger = MultiplayerEventLogger()
        self.spectator_sync_manager: Optional[SpectatorSyncManager] = None
        # 实时数据推送任务管理
        self.leaderboard_tasks: Dict[int, asyncio.Task] = {}
        # 观战状态同步任务
        self.spectator_sync_tasks: Dict[int, asyncio.Task] = {}
        
    async def initialize_managers(self):
        """初始化管理器"""
        if not self.spectator_sync_manager:
            redis = get_redis()
            self.spectator_sync_manager = SpectatorSyncManager(redis)
            
            # 启动观战事件监听
            asyncio.create_task(self.spectator_sync_manager.subscribe_to_spectator_events(
                self._handle_spectator_event
            ))

    async def _handle_spectator_event(self, channel: str, data: Dict):
        """处理观战事件"""
        try:
            room_id = data.get('room_id')
            event_type = data.get('event_type')
            event_data = data.get('data', {})
            
            if room_id and event_type and room_id in self.rooms:
                server_room = self.rooms[room_id]
                await self._process_spectator_event(server_room, event_type, event_data)
        except Exception as e:
            logger.error(f"Error handling spectator event: {e}")

    async def _process_spectator_event(self, server_room: ServerMultiplayerRoom, event_type: str, event_data: Dict):
        """处理具体的观战事件"""
        room_id = server_room.room.room_id
        
        if event_type == "spectator_joined":
            user_id = event_data.get('user_id')
            if user_id:
                await self._sync_spectator_with_current_state(room_id, user_id)
        
        elif event_type == "request_leaderboard":
            user_id = event_data.get('user_id')
            if user_id:
                leaderboard = gameplay_buffer.get_leaderboard(room_id)
                await self._send_leaderboard_to_spectator(user_id, leaderboard)

    async def _sync_spectator_with_current_state(self, room_id: int, user_id: int):
        """同步观战者与当前游戏状态"""
        try:
            snapshot = gameplay_buffer.get_gameplay_snapshot(room_id)
            if snapshot:
                # 通过Redis发送状态同步信息给SpectatorHub
                redis = get_redis()
                sync_data = {
                    'target_user': user_id,
                    'snapshot': snapshot,
                    'timestamp': datetime.now(UTC).isoformat()
                }
                await redis.publish(f"spectator_sync:{room_id}", json.dumps(sync_data))
        except Exception as e:
            logger.error(f"Error syncing spectator {user_id} with room {room_id}: {e}")

    async def _send_leaderboard_to_spectator(self, user_id: int, leaderboard: List[Dict]):
        """发送排行榜数据给观战者"""
        try:
            redis = get_redis()
            leaderboard_data = {
                'target_user': user_id,
                'leaderboard': leaderboard,
                'timestamp': datetime.now(UTC).isoformat()
            }
            await redis.publish(f"leaderboard_update:{user_id}", json.dumps(leaderboard_data))
        except Exception as e:
            logger.error(f"Error sending leaderboard to spectator {user_id}: {e}")

    @staticmethod
    def group_id(room: int) -> str:
        return f"room:{room}"

    @override
    def create_state(self, client: Client) -> MultiplayerClientState:
        return MultiplayerClientState(
            connection_id=client.connection_id,
            connection_token=client.connection_token,
        )

    @override
    async def _clean_state(self, state: MultiplayerClientState):
        user_id = int(state.connection_id)

        # Use centralized offline status management
        from app.service.online_status_manager import online_status_manager
        await online_status_manager.set_user_offline(user_id)

        if state.room_id != 0 and state.room_id in self.rooms:
            server_room = self.rooms[state.room_id]
            room = server_room.room
            user = next((u for u in room.users if u.user_id == user_id), None)
            if user is not None:
                await self.make_user_leave(
                    self.get_client_by_id(str(user_id)), server_room, user
                )

    async def on_client_connect(self, client: Client) -> None:
        """Track online users when connecting to multiplayer hub"""
        logger.info(f"[MultiplayerHub] Client {client.user_id} connected")

        # Use centralized online status management
        from app.service.online_status_manager import online_status_manager
        await online_status_manager.set_user_online(client.user_id, "multiplayer")

    def _ensure_in_room(self, client: Client) -> ServerMultiplayerRoom:
        store = self.get_or_create_state(client)
        if store.room_id == 0:
            raise InvokeException("You are not in a room")
        if store.room_id not in self.rooms:
            raise InvokeException("Room does not exist")
        server_room = self.rooms[store.room_id]
        return server_room

    def _ensure_host(self, client: Client, server_room: ServerMultiplayerRoom):
        room = server_room.room
        if room.host is None or room.host.user_id != client.user_id:
            raise InvokeException("You are not the host of this room")

    async def CreateRoom(self, client: Client, room: MultiplayerRoom):
        logger.info(f"[MultiplayerHub] {client.user_id} creating room")
        store = self.get_or_create_state(client)
        if store.room_id != 0:
            raise InvokeException("You are already in a room")
        async with with_db() as session:
            async with session:
                db_room = Room(
                    name=room.settings.name,
                    category=RoomCategory.REALTIME,
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

                channel = ChatChannel(
                    name=f"room_{db_room.id}",
                    description="Multiplayer room",
                    type=ChannelType.MULTIPLAYER,
                )
                session.add(channel)
                await session.commit()
                await session.refresh(channel)
                await session.refresh(db_room)
                room.channel_id = channel.channel_id  # pyright: ignore[reportAttributeAccessIssue]
                db_room.channel_id = channel.channel_id

                item = room.playlist[0]
                item.owner_id = client.user_id
                room.room_id = db_room.id
                starts_at = db_room.starts_at or datetime.now(UTC)
                beatmap_exists = await session.exec(
                    select(exists().where(col(Beatmap.id) == item.beatmap_id))
                )
                if not beatmap_exists.one():
                    fetcher = await get_fetcher()
                    try:
                        await Beatmap.get_or_fetch(
                            session, fetcher, bid=item.beatmap_id
                        )
                    except HTTPError:
                        raise InvokeException(
                            "Failed to fetch beatmap, please retry later"
                        )
                await Playlist.add_to_db(item, room.room_id, session)

                server_room = ServerMultiplayerRoom(
                    room=room,
                    category=RoomCategory.NORMAL,
                    start_at=starts_at,
                    hub=self,
                )
                self.rooms[room.room_id] = server_room
                await server_room.set_handler()
                await self.event_logger.room_created(room.room_id, client.user_id)
                return await self.JoinRoomWithPassword(
                    client, room.room_id, room.settings.password
                )

    async def JoinRoom(self, client: Client, room_id: int):
        return self.JoinRoomWithPassword(client, room_id, "")

    async def JoinRoomWithPassword(self, client: Client, room_id: int, password: str):
        logger.info(f"[MultiplayerHub] {client.user_id} joining room {room_id}")
        
        # 初始化管理器
        await self.initialize_managers()
        
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
        await server_room.match_type_handler.handle_join(user)

        # Enhanced: Send current room and gameplay state to new user
        # This ensures spectators joining ongoing games get proper state sync
        await self._send_room_state_to_new_user(client, server_room)
        
        # 如果正在进行游戏，同步游戏状态
        if room.state in [MultiplayerRoomState.PLAYING, MultiplayerRoomState.WAITING_FOR_LOAD]:
            await self._sync_new_user_with_gameplay(client, server_room)

        await self.event_logger.player_joined(room_id, user.user_id)

        async with with_db() as session:
            async with session.begin():
                if (
                    participated_user := (
                        await session.exec(
                            select(RoomParticipatedUser).where(
                                RoomParticipatedUser.room_id == room_id,
                                RoomParticipatedUser.user_id == client.user_id,
                            )
                        )
                    ).first()
                ) is None:
                    participated_user = RoomParticipatedUser(
                        room_id=room_id,
                        user_id=client.user_id,
                    )
                    session.add(participated_user)
                else:
                    participated_user.left_at = None
                    participated_user.joined_at = datetime.now(UTC)

                db_room = await session.get(Room, room_id)
                if db_room is None:
                    raise InvokeException("Room does not exist in database")
                db_room.participant_count += 1

        redis = get_redis()
        await redis.publish("chat:room:joined", f"{room.channel_id}:{user.user_id}")
        
        # 通知观战Hub有新用户加入
        if self.spectator_sync_manager:
            await self.spectator_sync_manager.notify_spectator_hubs(
                room_id, "user_joined", {'user_id': user.user_id}
            )

        return room

    async def _sync_new_user_with_gameplay(self, client: Client, room: ServerMultiplayerRoom):
        """同步新用户与正在进行的游戏状态"""
        try:
            room_id = room.room.room_id
            
            # 获取游戏状态快照
            snapshot = gameplay_buffer.get_gameplay_snapshot(room_id)
            if not snapshot:
                # 创建新的快照
                room_data = {
                    'state': room.room.state,
                    'current_item': room.queue.current_item,
                    'users': [{'user_id': u.user_id, 'state': u.state} for u in room.room.users]
                }
                snapshot = await gameplay_buffer.create_gameplay_snapshot(room_id, room_data)
            
            # 发送游戏状态到新用户
            await self.broadcast_call(client.connection_id, "GameplayStateSync", snapshot)
            
            # 发送实时排行榜
            leaderboard = gameplay_buffer.get_leaderboard(room_id)
            if leaderboard:
                await self.broadcast_call(client.connection_id, "LeaderboardUpdate", leaderboard)
            
            logger.info(f"[MultiplayerHub] Synced gameplay state for user {client.user_id} in room {room_id}")
        except Exception as e:
            logger.error(f"Error syncing new user with gameplay: {e}")

        return room

    async def change_beatmap_availability(
        self,
        room_id: int,
        user: MultiplayerRoomUser,
        beatmap_availability: BeatmapAvailability,
    ):
        availability = user.availability
        if (
            availability.state == beatmap_availability.state
            and availability.download_progress == beatmap_availability.download_progress
        ):
            return
        user.availability = beatmap_availability
        await self.broadcast_group_call(
            self.group_id(room_id),
            "UserBeatmapAvailabilityChanged",
            user.user_id,
            beatmap_availability,
        )

    async def ChangeBeatmapAvailability(
        self, client: Client, beatmap_availability: BeatmapAvailability
    ):
        server_room = self._ensure_in_room(client)
        room = server_room.room
        user = next((u for u in room.users if u.user_id == client.user_id), None)
        if user is None:
            raise InvokeException("You are not in this room")
        await self.change_beatmap_availability(
            room.room_id,
            user,
            beatmap_availability,
        )

    async def AddPlaylistItem(self, client: Client, item: PlaylistItem):
        server_room = self._ensure_in_room(client)
        room = server_room.room

        user = next((u for u in room.users if u.user_id == client.user_id), None)
        if user is None:
            raise InvokeException("You are not in this room")
        logger.info(
            f"[MultiplayerHub] {client.user_id} adding "
            f"beatmap {item.beatmap_id} to room {room.room_id}"
        )
        await server_room.queue.add_item(
            item,
            user,
        )

    async def EditPlaylistItem(self, client: Client, item: PlaylistItem):
        server_room = self._ensure_in_room(client)
        room = server_room.room

        user = next((u for u in room.users if u.user_id == client.user_id), None)
        if user is None:
            raise InvokeException("You are not in this room")

        logger.info(
            f"[MultiplayerHub] {client.user_id} editing "
            f"item {item.id} in room {room.room_id}"
        )
        await server_room.queue.edit_item(
            item,
            user,
        )

    async def RemovePlaylistItem(self, client: Client, item_id: int):
        server_room = self._ensure_in_room(client)
        room = server_room.room

        user = next((u for u in room.users if u.user_id == client.user_id), None)
        if user is None:
            raise InvokeException("You are not in this room")

        logger.info(
            f"[MultiplayerHub] {client.user_id} removing "
            f"item {item_id} from room {room.room_id}"
        )
        await server_room.queue.remove_item(
            item_id,
            user,
        )

    async def change_db_settings(self, room: ServerMultiplayerRoom):
        async with with_db() as session:
            await session.execute(
                update(Room)
                .where(col(Room.id) == room.room.room_id)
                .values(
                    name=room.room.settings.name,
                    type=room.room.settings.match_type,
                    queue_mode=room.room.settings.queue_mode,
                    auto_skip=room.room.settings.auto_skip,
                    auto_start_duration=int(
                        room.room.settings.auto_start_duration.total_seconds()
                    ),
                    host_id=room.room.host.user_id if room.room.host else None,
                )
            )
            await session.commit()

    async def setting_changed(self, room: ServerMultiplayerRoom, beatmap_changed: bool):
        await self.change_db_settings(room)
        await self.validate_styles(room)
        await self.unready_all_users(room, beatmap_changed)
        await self.broadcast_group_call(
            self.group_id(room.room.room_id),
            "SettingsChanged",
            room.room.settings,
        )

    async def playlist_added(self, room: ServerMultiplayerRoom, item: PlaylistItem):
        await self.broadcast_group_call(
            self.group_id(room.room.room_id),
            "PlaylistItemAdded",
            item,
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
        if item.id == room.room.settings.playlist_item_id:
            await self.validate_styles(room)
            await self.unready_all_users(room, beatmap_changed)
        await self.broadcast_group_call(
            self.group_id(room.room.room_id),
            "PlaylistItemChanged",
            item,
        )

    async def ChangeUserStyle(
        self, client: Client, beatmap_id: int | None, ruleset_id: int | None
    ):
        server_room = self._ensure_in_room(client)
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
        fetcher = await get_fetcher()
        if not room.queue.current_item.freestyle:
            for user in room.room.users:
                await self.change_user_style(
                    None,
                    None,
                    room,
                    user,
                )
        async with with_db() as session:
            try:
                beatmap = await Beatmap.get_or_fetch(
                    session, fetcher, bid=room.queue.current_item.beatmap_id
                )
            except HTTPError:
                raise InvokeException("Current item beatmap not found")
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
            if not room.queue.current_item.freestyle:
                raise InvokeException("Current item does not allow free user styles.")

            async with with_db() as session:
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
                    and ruleset_id != int(user_beatmap.mode)
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
        server_room = self._ensure_in_room(client)
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
                raise InvokeException(f"Cannot change state from {old} to {new}")
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
                # Allow server-managed transitions to RESULTS state
                # This includes spectators who need to see results
                if old not in (
                    MultiplayerUserState.FINISHED_PLAY,
                    MultiplayerUserState.SPECTATING,  # Allow spectators to see results
                ):
                    raise InvokeException(f"Cannot change state from {old} to {new}")
            case MultiplayerUserState.SPECTATING:
                # Enhanced spectator validation - allow transitions from more states
                # This matches official osu-server-spectator behavior
                if old not in (
                    MultiplayerUserState.IDLE,
                    MultiplayerUserState.READY,
                    MultiplayerUserState.RESULTS,  # Allow spectating after results
                ):
                    # Allow spectating during gameplay states only if the room is in appropriate state
                    if not (
                        old.is_playing
                        and room.room.state
                        in (
                            MultiplayerRoomState.WAITING_FOR_LOAD,
                            MultiplayerRoomState.PLAYING,
                        )
                    ):
                        raise InvokeException(
                            f"Cannot change state from {old} to {new}"
                        )
            case _:
                raise InvokeException(f"Invalid state transition from {old} to {new}")

    async def ChangeState(self, client: Client, state: MultiplayerUserState):
        server_room = self._ensure_in_room(client)
        room = server_room.room
        user = next((u for u in room.users if u.user_id == client.user_id), None)
        if user is None:
            raise InvokeException("You are not in this room")

        if user.state == state:
            return

        # 记录状态变化用于观战同步
        old_state = user.state

        # Special handling for state changes during gameplay
        match state:
            case MultiplayerUserState.IDLE:
                if user.state.is_playing:
                    # 玩家退出游戏时，清理分数缓冲区
                    room_id = room.room_id
                    if room_id in gameplay_buffer.score_buffers:
                        gameplay_buffer.score_buffers[room_id].pop(user.user_id, None)
                        await gameplay_buffer._update_leaderboard(room_id)
                        await self._broadcast_leaderboard_update(server_room)
                    return
            case MultiplayerUserState.LOADED | MultiplayerUserState.READY_FOR_GAMEPLAY:
                if not user.state.is_playing:
                    return
            case MultiplayerUserState.PLAYING:
                # 开始游戏时初始化分数缓冲区
                room_id = room.room_id
                await gameplay_buffer.add_score_frame(room_id, user.user_id, {
                    'score': 0,
                    'combo': 0,
                    'accuracy': 100.0,
                    'completed': False
                })

        logger.info(
            f"[MultiplayerHub] User {user.user_id} changing state from {user.state} to {state}"
        )

        await self.validate_user_stare(
            server_room,
            user.state,
            state,
        )

        await self.change_user_state(server_room, user, state)

        # Enhanced spectator handling based on official implementation
        if state == MultiplayerUserState.SPECTATING:
            await self.handle_spectator_state_change(client, server_room, user)

        # 通知观战Hub状态变化
        if self.spectator_sync_manager:
            await self.spectator_sync_manager.notify_user_state_change(
                room.room_id, user.user_id, old_state.name, state.name
            )

        await self.update_room_state(server_room)

    async def _broadcast_leaderboard_update(self, room: ServerMultiplayerRoom):
        """广播实时排行榜更新"""
        try:
            room_id = room.room.room_id
            leaderboard = gameplay_buffer.get_leaderboard(room_id)
            
            if leaderboard:
                await self.broadcast_group_call(
                    self.group_id(room_id),
                    "LeaderboardUpdate",
                    leaderboard
                )
                
                logger.debug(f"[MultiplayerHub] Broadcasted leaderboard update to room {room_id}")
        except Exception as e:
            logger.error(f"Error broadcasting leaderboard update: {e}")

    async def _start_leaderboard_broadcast_task(self, room_id: int):
        """启动实时排行榜广播任务"""
        if room_id in self.leaderboard_tasks:
            return
            
        async def leaderboard_broadcast_loop():
            try:
                while room_id in self.rooms and room_id in self.leaderboard_tasks:
                    if room_id in self.rooms:
                        server_room = self.rooms[room_id]
                        if server_room.room.state == MultiplayerRoomState.PLAYING:
                            await self._broadcast_leaderboard_update(server_room)
                    
                    await asyncio.sleep(1.0)  # 每秒更新一次排行榜
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"Error in leaderboard broadcast loop for room {room_id}: {e}")
        
        task = asyncio.create_task(leaderboard_broadcast_loop())
        self.leaderboard_tasks[room_id] = task

    async def _stop_leaderboard_broadcast_task(self, room_id: int):
        """停止实时排行榜广播任务"""
        if room_id in self.leaderboard_tasks:
            task = self.leaderboard_tasks.pop(room_id)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def change_user_state(
        self,
        room: ServerMultiplayerRoom,
        user: MultiplayerRoomUser,
        state: MultiplayerUserState,
    ):
        logger.info(
            f"[MultiplayerHub] {user.user_id}'s state "
            f"changed from {user.state} to {state}"
        )
        user.state = state
        await self.broadcast_group_call(
            self.group_id(room.room.room_id),
            "UserStateChanged",
            user.user_id,
            user.state,
        )

    async def handle_spectator_state_change(
        self, client: Client, room: ServerMultiplayerRoom, user: MultiplayerRoomUser
    ):
        """
        Handle special logic for users entering spectator mode during ongoing gameplay.
        Based on official osu-server-spectator implementation.
        """
        room_state = room.room.state

        # If switching to spectating during gameplay, immediately request load
        if room_state == MultiplayerRoomState.WAITING_FOR_LOAD:
            logger.info(
                f"[MultiplayerHub] Spectator {user.user_id} joining during load phase"
            )
            await self.call_noblock(client, "LoadRequested")

        elif room_state == MultiplayerRoomState.PLAYING:
            logger.info(
                f"[MultiplayerHub] Spectator {user.user_id} joining during active gameplay"
            )
            await self.call_noblock(client, "LoadRequested")
            
        # Also sync the spectator with current game state
        await self._send_current_gameplay_state_to_spectator(client, room)

    async def _send_current_gameplay_state_to_spectator(
        self, client: Client, room: ServerMultiplayerRoom
    ):
        """
        Send current gameplay state information to a newly joined spectator.
        This helps spectators sync with ongoing gameplay.
        """
        try:
            # Send current room state
            await self.call_noblock(client, "RoomStateChanged", room.room.state)

            # Send current user states for all players
            for room_user in room.room.users:
                if room_user.state.is_playing or room_user.state == MultiplayerUserState.RESULTS:
                    await self.call_noblock(
                        client,
                        "UserStateChanged",
                        room_user.user_id,
                        room_user.state,
                    )
                    
            # If the room is in OPEN state but we have users in RESULTS state,
            # this means the game just finished and we should send ResultsReady
            if (room.room.state == MultiplayerRoomState.OPEN and 
                any(u.state == MultiplayerUserState.RESULTS for u in room.room.users)):
                logger.debug(
                    f"[MultiplayerHub] Sending ResultsReady to new spectator {client.user_id}"
                )
                await self.call_noblock(client, "ResultsReady")

            logger.debug(
                f"[MultiplayerHub] Sent current gameplay state to spectator {client.user_id}"
            )
        except Exception as e:
            logger.error(
                f"[MultiplayerHub] Failed to send gameplay state to spectator {client.user_id}: {e}"
            )

    async def _send_room_state_to_new_user(
        self, client: Client, room: ServerMultiplayerRoom
    ):
        """
        Send complete room state to a newly joined user.
        Critical for spectators joining ongoing games.
        """
        try:
            # Send current room state
            if room.room.state != MultiplayerRoomState.OPEN:
                await self.call_noblock(client, "RoomStateChanged", room.room.state)

            # If room is in gameplay state, send LoadRequested immediately
            if room.room.state in (
                MultiplayerRoomState.WAITING_FOR_LOAD,
                MultiplayerRoomState.PLAYING,
            ):
                logger.info(
                    f"[MultiplayerHub] Sending LoadRequested to user {client.user_id} "
                    f"joining ongoing game (room state: {room.room.state})"
                )
                await self.call_noblock(client, "LoadRequested")

            # Send all user states to help with synchronization
            for room_user in room.room.users:
                if room_user.user_id != client.user_id:  # Don't send own state
                    await self.call_noblock(
                        client,
                        "UserStateChanged",
                        room_user.user_id,
                        room_user.state,
                    )

            # Critical fix: If room is OPEN but has users in RESULTS state,
            # send ResultsReady to new joiners (including spectators)
            if (room.room.state == MultiplayerRoomState.OPEN and 
                any(u.state == MultiplayerUserState.RESULTS for u in room.room.users)):
                logger.info(
                    f"[MultiplayerHub] Sending ResultsReady to newly joined user {client.user_id}"
                )
                await self.call_noblock(client, "ResultsReady")

            # Critical addition: Send current playing users to SpectatorHub for cross-hub sync
            # This ensures spectators can watch multiplayer players properly
            await self._sync_with_spectator_hub(client, room)

            logger.debug(
                f"[MultiplayerHub] Sent complete room state to new user {client.user_id}"
            )
        except Exception as e:
            logger.error(
                f"[MultiplayerHub] Failed to send room state to user {client.user_id}: {e}"
            )

    async def _sync_with_spectator_hub(
        self, client: Client, room: ServerMultiplayerRoom
    ):
        """
        Sync with SpectatorHub to ensure cross-hub spectating works properly.
        This is crucial for users watching multiplayer players from other pages.
        """
        try:
            # Import here to avoid circular imports
            from app.signalr.hub import SpectatorHubs

            # For each user in the room, check their state and sync appropriately
            for room_user in room.room.users:
                if room_user.state.is_playing:
                    spectator_state = SpectatorHubs.state.get(room_user.user_id)
                    if spectator_state and spectator_state.state:
                        # Send the spectator state to help with cross-hub watching
                        await self.call_noblock(
                            client,
                            "UserBeganPlaying",
                            room_user.user_id,
                            spectator_state.state,
                        )
                        logger.debug(
                            f"[MultiplayerHub] Synced spectator state for user {room_user.user_id} "
                            f"to new client {client.user_id}"
                        )
                
                # Critical addition: Notify SpectatorHub about users in RESULTS state
                elif room_user.state == MultiplayerUserState.RESULTS:
                    # Create a synthetic finished state for cross-hub spectating
                    try:
                        from app.models.spectator_hub import SpectatedUserState, SpectatorState
                        
                        finished_state = SpectatorState(
                            beatmap_id=room.queue.current_item.beatmap_id,
                            ruleset_id=room_user.ruleset_id or 0,
                            mods=room_user.mods,
                            state=SpectatedUserState.Passed,  # Assume passed for results
                            maximum_statistics={},
                        )

                        await self.call_noblock(
                            client,
                            "UserFinishedPlaying",
                            room_user.user_id,
                            finished_state,
                        )
                        logger.debug(
                            f"[MultiplayerHub] Sent synthetic finished state for user {room_user.user_id} "
                            f"to client {client.user_id}"
                        )
                    except Exception as e:
                        logger.debug(
                            f"[MultiplayerHub] Failed to create synthetic finished state: {e}"
                        )

        except Exception as e:
            logger.debug(f"[MultiplayerHub] Failed to sync with SpectatorHub: {e}")
            # This is not critical, so we don't raise the exception

    async def update_room_state(self, room: ServerMultiplayerRoom):
        match room.room.state:
            case MultiplayerRoomState.OPEN:
                if room.room.settings.auto_start_enabled:
                    if (
                        not room.queue.current_item.expired
                        and any(
                            u.state == MultiplayerUserState.READY
                            for u in room.room.users
                        )
                        and not any(
                            isinstance(countdown, MatchStartCountdown)
                            for countdown in room.room.active_countdowns
                        )
                    ):
                        await room.start_countdown(
                            MatchStartCountdown(
                                time_remaining=room.room.settings.auto_start_duration
                            ),
                            self.start_match,
                        )
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
                if all(
                    u.state != MultiplayerUserState.PLAYING for u in room.room.users
                ):
                    any_user_finished_playing = False
                    
                    # Handle finished players first
                    for u in filter(
                        lambda u: u.state == MultiplayerUserState.FINISHED_PLAY,
                        room.room.users,
                    ):
                        any_user_finished_playing = True
                        await self.change_user_state(
                            room, u, MultiplayerUserState.RESULTS
                        )
                    
                    # Critical fix: Handle spectators who should also see results
                    # Move spectators to RESULTS state so they can see the results screen
                    for u in filter(
                        lambda u: u.state == MultiplayerUserState.SPECTATING,
                        room.room.users,
                    ):
                        logger.debug(
                            f"[MultiplayerHub] Moving spectator {u.user_id} to RESULTS state"
                        )
                        await self.change_user_state(
                            room, u, MultiplayerUserState.RESULTS
                        )
                    
                    await self.change_room_state(room, MultiplayerRoomState.OPEN)
                    
                    # Send ResultsReady to all room members
                    await self.broadcast_group_call(
                        self.group_id(room.room.room_id),
                        "ResultsReady",
                    )
                    
                    # Critical addition: Notify SpectatorHub about finished games
                    # This ensures cross-hub spectating works properly
                    await self._notify_spectator_hub_game_ended(room)
                    
                    if any_user_finished_playing:
                        await self.event_logger.game_completed(
                            room.room.room_id,
                            room.queue.current_item.id,
                        )
                    else:
                        await self.event_logger.game_aborted(
                            room.room.room_id,
                            room.queue.current_item.id,
                        )
                    await room.queue.finish_current_item()

    async def change_room_state(
        self, room: ServerMultiplayerRoom, state: MultiplayerRoomState
    ):
        old_state = room.room.state
        room_id = room.room.room_id
        
        logger.debug(
            f"[MultiplayerHub] Room {room_id} state "
            f"changed from {old_state} to {state}"
        )
        
        room.room.state = state
        await self.broadcast_group_call(
            self.group_id(room_id),
            "RoomStateChanged",
            state,
        )
        
        # 处理状态变化的特殊逻辑
        if old_state == MultiplayerRoomState.PLAYING and state == MultiplayerRoomState.OPEN:
            # 游戏结束，停止实时排行榜广播
            await self._stop_leaderboard_broadcast_task(room_id)
            
            # 发送最终排行榜
            leaderboard = gameplay_buffer.get_leaderboard(room_id)
            if leaderboard:
                await self.broadcast_group_call(
                    self.group_id(room_id),
                    "FinalLeaderboard",
                    leaderboard
                )
            
            # 通知观战Hub游戏结束
            if self.spectator_sync_manager:
                await self.spectator_sync_manager.notify_gameplay_ended(room_id, {
                    'leaderboard': leaderboard
                })
        
        elif state == MultiplayerRoomState.PLAYING:
            # 游戏开始，启动实时排行榜
            await self._start_leaderboard_broadcast_task(room_id)

    async def StartMatch(self, client: Client):
        server_room = self._ensure_in_room(client)
        room = server_room.room
        user = next((u for u in room.users if u.user_id == client.user_id), None)
        if user is None:
            raise InvokeException("You are not in this room")
        self._ensure_host(client, server_room)

        # Check host state - host must be ready or spectating
        if room.host and room.host.state not in (
            MultiplayerUserState.SPECTATING,
            MultiplayerUserState.READY,
        ):
            raise InvokeException("Can't start match when the host is not ready.")

        # Check if any users are ready
        if all(u.state != MultiplayerUserState.READY for u in room.users):
            raise InvokeException("Can't start match when no users are ready.")

        await self.start_match(server_room)

    async def start_match(self, room: ServerMultiplayerRoom):
        if room.room.state != MultiplayerRoomState.OPEN:
            raise InvokeException("Can't start match when already in a running state.")
        if room.queue.current_item.expired:
            raise InvokeException("Current playlist item is expired")

        if all(u.state != MultiplayerUserState.READY for u in room.room.users):
            await room.queue.finish_current_item()

        logger.info(f"[MultiplayerHub] Room {room.room.room_id} match started")

        ready_users = [
            u
            for u in room.room.users
            if u.availability.state == DownloadState.LOCALLY_AVAILABLE
            and (
                u.state == MultiplayerUserState.READY
                or u.state == MultiplayerUserState.IDLE
            )
        ]
        for u in ready_users:
            await self.change_user_state(room, u, MultiplayerUserState.WAITING_FOR_LOAD)
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
                time_remaining=timedelta(seconds=GAMEPLAY_LOAD_TIMEOUT)
            ),
            self.start_gameplay,
        )
        await self.event_logger.game_started(
            room.room.room_id,
            room.queue.current_item.id,
            details=room.match_type_handler.get_details(),
        )

    async def start_gameplay(self, room: ServerMultiplayerRoom):
        if room.room.state != MultiplayerRoomState.WAITING_FOR_LOAD:
            raise InvokeException("Room is not ready for gameplay")
        if room.queue.current_item.expired:
            raise InvokeException("Current playlist item is expired")
        await room.stop_all_countdowns(ForceGameplayStartCountdown)
        playing = False
        played_user = 0
        room_id = room.room.room_id
        
        for user in room.room.users:
            client = self.get_client_by_id(str(user.user_id))
            if client is None:
                continue

            if user.state in (
                MultiplayerUserState.READY_FOR_GAMEPLAY,
                MultiplayerUserState.LOADED,
            ):
                playing = True
                played_user += 1
                await self.change_user_state(room, user, MultiplayerUserState.PLAYING)
                await self.call_noblock(client, "GameplayStarted")
                
                # 初始化玩家分数缓冲区
                await gameplay_buffer.add_score_frame(room_id, user.user_id, {
                    'score': 0,
                    'combo': 0,
                    'accuracy': 100.0,
                    'completed': False
                })
                
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
        
        if playing:
            # 创建游戏状态快照
            room_data = {
                'state': room.room.state,
                'current_item': room.queue.current_item,
                'users': [{'user_id': u.user_id, 'state': u.state} for u in room.room.users]
            }
            await gameplay_buffer.create_gameplay_snapshot(room_id, room_data)
            
            # 启动实时排行榜广播
            await self._start_leaderboard_broadcast_task(room_id)
            
            # 通知观战Hub游戏开始
            if self.spectator_sync_manager:
                await self.spectator_sync_manager.notify_gameplay_started(room_id, room_data)
            
            redis = get_redis()
            await redis.set(
                f"multiplayer:{room.room.room_id}:gameplay:players",
                played_user,
                ex=3600,
            )
        else:
            await room.queue.finish_current_item()

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
        client: Client | None,
        room: ServerMultiplayerRoom,
        user: MultiplayerRoomUser,
        kicked: bool = False,
    ):
        if client:
            self.remove_from_group(client, self.group_id(room.room.room_id))
        room.room.users.remove(user)

        target_store = self.state.get(user.user_id)
        if target_store:
            target_store.room_id = 0

        redis = get_redis()
        await redis.publish("chat:room:left", f"{room.room.channel_id}:{user.user_id}")

        async with with_db() as session:
            async with session.begin():
                participated_user = (
                    await session.exec(
                        select(RoomParticipatedUser).where(
                            RoomParticipatedUser.room_id == room.room.room_id,
                            RoomParticipatedUser.user_id == user.user_id,
                        )
                    )
                ).first()
                if participated_user is not None:
                    participated_user.left_at = datetime.now(UTC)

                db_room = await session.get(Room, room.room.room_id)
                if db_room is None:
                    raise InvokeException("Room does not exist in database")
                if db_room.participant_count > 0:
                    db_room.participant_count -= 1

        if len(room.room.users) == 0:
            await self.end_room(room)
            return
        await self.update_room_state(room)
        if (
            len(room.room.users) != 0
            and room.room.host
            and room.room.host.user_id == user.user_id
        ):
            next_host = room.room.users[0]
            await self.set_host(room, next_host)

        if kicked:
            if client:
                await self.call_noblock(client, "UserKicked", user)
            await self.broadcast_group_call(
                self.group_id(room.room.room_id), "UserKicked", user
            )
        else:
            await self.broadcast_group_call(
                self.group_id(room.room.room_id), "UserLeft", user
            )

    async def end_room(self, room: ServerMultiplayerRoom):
        assert room.room.host
        async with with_db() as session:
            await session.execute(
                update(Room)
                .where(col(Room.id) == room.room.room_id)
                .values(
                    name=room.room.settings.name,
                    ends_at=datetime.now(UTC),
                    type=room.room.settings.match_type,
                    queue_mode=room.room.settings.queue_mode,
                    auto_skip=room.room.settings.auto_skip,
                    auto_start_duration=int(
                        room.room.settings.auto_start_duration.total_seconds()
                    ),
                    host_id=room.room.host.user_id,
                )
            )
        await self.event_logger.room_disbanded(
            room.room.room_id,
            room.room.host.user_id,
        )
        
        room_id = room.room.room_id
        
        # 清理实时数据
        await self._stop_leaderboard_broadcast_task(room_id)
        await gameplay_buffer.cleanup_room(room_id)
        
        # 清理观战同步任务
        if room_id in self.spectator_sync_tasks:
            task = self.spectator_sync_tasks.pop(room_id)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        del self.rooms[room_id]
        logger.info(f"[MultiplayerHub] Room {room_id} ended")

    async def UpdateScore(self, client: Client, score_data: Dict):
        """接收并处理实时分数更新"""
        try:
            server_room = self._ensure_in_room(client)
            room = server_room.room
            user = next((u for u in room.users if u.user_id == client.user_id), None)
            
            if user is None:
                raise InvokeException("User not found in room")
            
            if room.state != MultiplayerRoomState.PLAYING:
                return
            
            if user.state != MultiplayerUserState.PLAYING:
                return
            
            room_id = room.room_id
            
            # 添加分数帧到缓冲区
            await gameplay_buffer.add_score_frame(room_id, client.user_id, {
                'score': score_data.get('score', 0),
                'combo': score_data.get('combo', 0),
                'accuracy': score_data.get('accuracy', 0.0),
                'completed': score_data.get('completed', False),
                'hp': score_data.get('hp', 1.0),
                'position': score_data.get('position', 0)
            })
            
        except Exception as e:
            logger.error(f"Error updating score for user {client.user_id}: {e}")

    async def GetLeaderboard(self, client: Client) -> List[Dict]:
        """获取当前房间的实时排行榜"""
        try:
            server_room = self._ensure_in_room(client)
            room_id = server_room.room.room_id
            return gameplay_buffer.get_leaderboard(room_id)
        except Exception as e:
            logger.error(f"Error getting leaderboard for user {client.user_id}: {e}")
            return []

    async def RequestSpectatorSync(self, client: Client):
        """观战者请求同步当前游戏状态"""
        try:
            server_room = self._ensure_in_room(client)
            room_id = server_room.room.room_id
            
            # 发送游戏状态快照
            snapshot = gameplay_buffer.get_gameplay_snapshot(room_id)
            if snapshot:
                await self.broadcast_call(client.connection_id, "GameplayStateSync", snapshot)
            
            # 发送当前排行榜
            leaderboard = gameplay_buffer.get_leaderboard(room_id)
            if leaderboard:
                await self.broadcast_call(client.connection_id, "LeaderboardUpdate", leaderboard)
            
            logger.info(f"[MultiplayerHub] Sent spectator sync to user {client.user_id}")
            
        except Exception as e:
            logger.error(f"Error handling spectator sync request: {e}")

    async def LeaveRoom(self, client: Client):
        store = self.get_or_create_state(client)
        if store.room_id == 0:
            return
        server_room = self._ensure_in_room(client)
        room = server_room.room
        user = next((u for u in room.users if u.user_id == client.user_id), None)
        if user is None:
            raise InvokeException("You are not in this room")

        await self.event_logger.player_left(
            room.room_id,
            user.user_id,
        )
        await self.make_user_leave(client, server_room, user)
        logger.info(f"[MultiplayerHub] {client.user_id} left room {room.room_id}")

    async def KickUser(self, client: Client, user_id: int):
        server_room = self._ensure_in_room(client)
        room = server_room.room
        self._ensure_host(client, server_room)

        if user_id == client.user_id:
            raise InvokeException("Can't kick self")

        user = next((u for u in room.users if u.user_id == user_id), None)
        if user is None:
            raise InvokeException("User not found in this room")

        await self.event_logger.player_kicked(
            room.room_id,
            user.user_id,
        )
        target_client = self.get_client_by_id(str(user.user_id))
        await self.make_user_leave(target_client, server_room, user, kicked=True)
        logger.info(
            f"[MultiplayerHub] {user.user_id} was kicked from room {room.room_id}"
            f"by {client.user_id}"
        )

    async def set_host(self, room: ServerMultiplayerRoom, user: MultiplayerRoomUser):
        room.room.host = user
        await self.change_db_settings(room)
        await self.broadcast_group_call(
            self.group_id(room.room.room_id),
            "HostChanged",
            user.user_id,
        )

    async def TransferHost(self, client: Client, user_id: int):
        server_room = self._ensure_in_room(client)
        room = server_room.room
        self._ensure_host(client, server_room)

        new_host = next((u for u in room.users if u.user_id == user_id), None)
        if new_host is None:
            raise InvokeException("User not found in this room")
        await self.event_logger.host_changed(
            room.room_id,
            new_host.user_id,
        )
        await self.set_host(server_room, new_host)
        logger.info(
            f"[MultiplayerHub] {client.user_id} transferred host to {new_host.user_id}"
            f" in room {room.room_id}"
        )

    async def AbortGameplay(self, client: Client):
        server_room = self._ensure_in_room(client)
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
        server_room = self._ensure_in_room(client)
        room = server_room.room
        self._ensure_host(client, server_room)

        if (
            room.state != MultiplayerRoomState.PLAYING
            and room.state != MultiplayerRoomState.WAITING_FOR_LOAD
        ):
            raise InvokeException("Cannot abort a match that hasn't started.")

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
        logger.info(
            f"[MultiplayerHub] {client.user_id} aborted match in room {room.room_id}"
        )

    async def change_user_match_state(
        self, room: ServerMultiplayerRoom, user: MultiplayerRoomUser
    ):
        await self.broadcast_group_call(
            self.group_id(room.room.room_id),
            "MatchUserStateChanged",
            user.user_id,
            user.match_state,
        )

    async def change_room_match_state(self, room: ServerMultiplayerRoom):
        await self.broadcast_group_call(
            self.group_id(room.room.room_id),
            "MatchRoomStateChanged",
            room.room.match_state,
        )

    async def ChangeSettings(self, client: Client, settings: MultiplayerRoomSettings):
        server_room = self._ensure_in_room(client)
        self._ensure_host(client, server_room)
        room = server_room.room

        if room.state != MultiplayerRoomState.OPEN:
            raise InvokeException("Cannot change settings while playing")

        if settings.match_type == MatchType.PLAYLISTS:
            raise InvokeException("Invalid match type selected")

        settings.playlist_item_id = room.settings.playlist_item_id
        previous_settings = room.settings
        room.settings = settings

        if previous_settings.match_type != settings.match_type:
            await server_room.set_handler()
        if previous_settings.queue_mode != settings.queue_mode:
            await server_room.queue.update_queue_mode()

        await self.setting_changed(server_room, beatmap_changed=False)
        await self.update_room_state(server_room)

    async def SendMatchRequest(self, client: Client, request: MatchRequest):
        server_room = self._ensure_in_room(client)
        room = server_room.room
        user = next((u for u in room.users if u.user_id == client.user_id), None)
        if user is None:
            raise InvokeException("You are not in this room")

        if isinstance(request, StartMatchCountdownRequest):
            if room.host and room.host.user_id != user.user_id:
                raise InvokeException("You are not the host of this room")
            if room.state != MultiplayerRoomState.OPEN:
                raise InvokeException("Cannot start match countdown when not open")
            await server_room.start_countdown(
                MatchStartCountdown(time_remaining=request.duration),
                self.start_match,
            )
        elif isinstance(request, StopCountdownRequest):
            countdown = next(
                (c for c in room.active_countdowns if c.id == request.id),
                None,
            )
            if countdown is None:
                return
            if (
                isinstance(countdown, MatchStartCountdown)
                and room.settings.auto_start_enabled
            ) or isinstance(
                countdown, (ForceGameplayStartCountdown | ServerShuttingDownCountdown)
            ):
                raise InvokeException("Cannot stop the requested countdown")

            await server_room.stop_countdown(countdown)
        else:
            await server_room.match_type_handler.handle_request(user, request)

    async def InvitePlayer(self, client: Client, user_id: int):
        server_room = self._ensure_in_room(client)
        room = server_room.room
        user = next((u for u in room.users if u.user_id == client.user_id), None)
        if user is None:
            raise InvokeException("You are not in this room")

        async with with_db() as session:
            db_user = await session.get(User, user_id)
            target_relationship = (
                await session.exec(
                    select(Relationship).where(
                        Relationship.user_id == user_id,
                        Relationship.target_id == client.user_id,
                    )
                )
            ).first()
            inviter_relationship = (
                await session.exec(
                    select(Relationship).where(
                        Relationship.user_id == client.user_id,
                        Relationship.target_id == user_id,
                    )
                )
            ).first()
            if db_user is None:
                raise InvokeException("User not found")
            if db_user.id == client.user_id:
                raise InvokeException("You cannot invite yourself")
            if db_user.id in [u.user_id for u in room.users]:
                raise InvokeException("User already invited")
            if db_user.is_restricted:
                raise InvokeException("User is restricted")
            if (
                inviter_relationship
                and inviter_relationship.type == RelationshipType.BLOCK
            ):
                raise InvokeException("Cannot perform action due to user being blocked")
            if (
                target_relationship
                and target_relationship.type == RelationshipType.BLOCK
            ):
                raise InvokeException("Cannot perform action due to user being blocked")
            if (
                db_user.pm_friends_only
                and target_relationship is not None
                and target_relationship.type != RelationshipType.FOLLOW
            ):
                raise InvokeException(
                    "Cannot perform action "
                    "because user has disabled non-friend communications"
                )

        target_client = self.get_client_by_id(str(user_id))
        if target_client is None:
            raise InvokeException("User is not online")
        await self.call_noblock(
            target_client,
            "Invited",
            client.user_id,
            room.room_id,
            room.settings.password,
        )

    async def unready_all_users(
        self, room: ServerMultiplayerRoom, reset_beatmap_availability: bool
    ):
        await asyncio.gather(
            *[
                self.change_user_state(
                    room,
                    user,
                    MultiplayerUserState.IDLE,
                )
                for user in room.room.users
                if user.state == MultiplayerUserState.READY
            ]
        )
        if reset_beatmap_availability:
            await asyncio.gather(
                *[
                    self.change_beatmap_availability(
                        room.room.room_id,
                        user,
                        BeatmapAvailability(state=DownloadState.UNKNOWN),
                    )
                    for user in room.room.users
                ]
            )
        await room.stop_all_countdowns(MatchStartCountdown)

    async def _notify_spectator_hub_game_ended(self, room: ServerMultiplayerRoom):
        """
        Notify SpectatorHub about ended multiplayer game.
        This ensures cross-hub spectating works properly when games end.
        """
        try:
            # Import here to avoid circular imports
            from app.signalr.hub import SpectatorHubs
            from app.models.spectator_hub import SpectatedUserState, SpectatorState

            # For each user who finished the game, notify SpectatorHub
            for room_user in room.room.users:
                if room_user.state == MultiplayerUserState.RESULTS:
                    # Create a synthetic finished state
                    finished_state = SpectatorState(
                        beatmap_id=room.queue.current_item.beatmap_id,
                        ruleset_id=room_user.ruleset_id or 0,
                        mods=room_user.mods,
                        state=SpectatedUserState.Passed,  # Assume passed for results
                        maximum_statistics={},
                    )

                    # Notify all SpectatorHub watchers that this user finished
                    await SpectatorHubs.broadcast_group_call(
                        SpectatorHubs.group_id(room_user.user_id),
                        "UserFinishedPlaying",
                        room_user.user_id,
                        finished_state,
                    )
                    
                    logger.debug(
                        f"[MultiplayerHub] Notified SpectatorHub that user {room_user.user_id} finished game"
                    )

        except Exception as e:
            logger.debug(
                f"[MultiplayerHub] Failed to notify SpectatorHub about game end: {e}"
            )
            # This is not critical, so we don't raise the exception
