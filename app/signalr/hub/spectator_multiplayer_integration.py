"""
SpectatorHub增强补丁
与MultiplayerHub集成以支持多人游戏观战
"""

from __future__ import annotations
import asyncio
import json
from datetime import datetime, UTC
from typing import Dict, Optional
from collections import defaultdict

from app.dependencies.database import get_redis
from app.log import logger


class SpectatorMultiplayerIntegration:
    """SpectatorHub的多人游戏集成扩展"""
    
    def __init__(self, spectator_hub_instance):
        self.hub = spectator_hub_instance
        self.redis = None
        self.multiplayer_subscribers = defaultdict(set)  # room_id -> set of connection_ids
        self.leaderboard_cache = {}  # room_id -> leaderboard data
        
    async def initialize(self):
        """初始化多人游戏集成"""
        self.redis = get_redis()
        
        # 启动Redis订阅任务
        asyncio.create_task(self._subscribe_to_multiplayer_events())
        asyncio.create_task(self._subscribe_to_leaderboard_updates())
        asyncio.create_task(self._subscribe_to_spectator_sync())
        
    async def _subscribe_to_multiplayer_events(self):
        """订阅多人游戏事件"""
        try:
            pubsub = self.redis.pubsub()
            await pubsub.psubscribe("multiplayer_spectator:*")
            
            async for message in pubsub.listen():
                if message['type'] == 'pmessage':
                    try:
                        data = json.loads(message['data'])
                        await self._handle_multiplayer_event(message['channel'], data)
                    except Exception as e:
                        logger.error(f"Error processing multiplayer event: {e}")
        except Exception as e:
            logger.error(f"Error in multiplayer events subscription: {e}")
    
    async def _subscribe_to_leaderboard_updates(self):
        """订阅排行榜更新"""
        try:
            pubsub = self.redis.pubsub()
            await pubsub.psubscribe("leaderboard_update:*")
            
            async for message in pubsub.listen():
                if message['type'] == 'pmessage':
                    try:
                        data = json.loads(message['data'])
                        user_id = message['channel'].split(':')[-1]
                        await self._send_leaderboard_to_user(int(user_id), data['leaderboard'])
                    except Exception as e:
                        logger.error(f"Error processing leaderboard update: {e}")
        except Exception as e:
            logger.error(f"Error in leaderboard updates subscription: {e}")
    
    async def _subscribe_to_spectator_sync(self):
        """订阅观战同步事件"""
        try:
            pubsub = self.redis.pubsub()
            await pubsub.psubscribe("spectator_sync:*")
            
            async for message in pubsub.listen():
                if message['type'] == 'pmessage':
                    try:
                        data = json.loads(message['data'])
                        room_id = message['channel'].split(':')[-1]
                        await self._handle_spectator_sync(int(room_id), data)
                    except Exception as e:
                        logger.error(f"Error processing spectator sync: {e}")
        except Exception as e:
            logger.error(f"Error in spectator sync subscription: {e}")
    
    async def _handle_multiplayer_event(self, channel: str, data: Dict):
        """处理多人游戏事件"""
        room_id = data.get('room_id')
        event_type = data.get('event_type')
        event_data = data.get('data', {})
        
        if not room_id or not event_type:
            return
            
        if event_type == "gameplay_started":
            await self._handle_gameplay_started(room_id, event_data)
        elif event_type == "gameplay_ended":
            await self._handle_gameplay_ended(room_id, event_data)
        elif event_type == "user_state_changed":
            await self._handle_user_state_changed(room_id, event_data)
    
    async def _handle_gameplay_started(self, room_id: int, game_data: Dict):
        """处理游戏开始事件"""
        logger.info(f"[SpectatorHub] Multiplayer game started in room {room_id}")
        
        # 通知所有观战该房间的用户
        if room_id in self.multiplayer_subscribers:
            for connection_id in self.multiplayer_subscribers[room_id]:
                await self._send_to_connection(connection_id, "MultiplayerGameStarted", game_data)
    
    async def _handle_gameplay_ended(self, room_id: int, results_data: Dict):
        """处理游戏结束事件"""
        logger.info(f"[SpectatorHub] Multiplayer game ended in room {room_id}")
        
        # 发送最终结果给观战者
        if room_id in self.multiplayer_subscribers:
            for connection_id in self.multiplayer_subscribers[room_id]:
                await self._send_to_connection(connection_id, "MultiplayerGameEnded", results_data)
    
    async def _handle_user_state_changed(self, room_id: int, state_data: Dict):
        """处理用户状态变化"""
        user_id = state_data.get('user_id')
        new_state = state_data.get('new_state')
        
        if room_id in self.multiplayer_subscribers:
            for connection_id in self.multiplayer_subscribers[room_id]:
                await self._send_to_connection(connection_id, "MultiplayerUserStateChanged", {
                    'user_id': user_id,
                    'state': new_state
                })
    
    async def _handle_spectator_sync(self, room_id: int, sync_data: Dict):
        """处理观战同步请求"""
        target_user = sync_data.get('target_user')
        snapshot = sync_data.get('snapshot')
        
        if target_user and snapshot:
            # 找到目标用户的连接并发送快照
            client = self.hub.get_client_by_id(str(target_user))
            if client:
                await self._send_to_connection(client.connection_id, "MultiplayerSnapshot", snapshot)
    
    async def _send_leaderboard_to_user(self, user_id: int, leaderboard: list):
        """发送排行榜给指定用户"""
        client = self.hub.get_client_by_id(str(user_id))
        if client:
            await self._send_to_connection(client.connection_id, "MultiplayerLeaderboard", leaderboard)
    
    async def _send_to_connection(self, connection_id: str, method: str, data):
        """发送数据到指定连接"""
        try:
            await self.hub.broadcast_call(connection_id, method, data)
        except Exception as e:
            logger.error(f"Error sending {method} to connection {connection_id}: {e}")
    
    async def subscribe_to_multiplayer_room(self, connection_id: str, room_id: int):
        """订阅多人游戏房间的观战"""
        self.multiplayer_subscribers[room_id].add(connection_id)
        
        # 通知MultiplayerHub有新的观战者
        await self.redis.publish(f"multiplayer_spectator:room:{room_id}", json.dumps({
            'event_type': 'spectator_joined',
            'data': {'user_id': self._get_user_id_from_connection(connection_id)},
            'room_id': room_id,
            'timestamp': datetime.now(UTC).isoformat()
        }))
        
        logger.info(f"[SpectatorHub] Connection {connection_id} subscribed to multiplayer room {room_id}")
    
    async def unsubscribe_from_multiplayer_room(self, connection_id: str, room_id: int):
        """取消订阅多人游戏房间"""
        if room_id in self.multiplayer_subscribers:
            self.multiplayer_subscribers[room_id].discard(connection_id)
            if not self.multiplayer_subscribers[room_id]:
                del self.multiplayer_subscribers[room_id]
        
        logger.info(f"[SpectatorHub] Connection {connection_id} unsubscribed from multiplayer room {room_id}")
    
    async def request_multiplayer_leaderboard(self, connection_id: str, room_id: int):
        """请求多人游戏排行榜"""
        user_id = self._get_user_id_from_connection(connection_id)
        if user_id:
            await self.redis.publish(f"multiplayer_spectator:room:{room_id}", json.dumps({
                'event_type': 'request_leaderboard',
                'data': {'user_id': user_id},
                'room_id': room_id,
                'timestamp': datetime.now(UTC).isoformat()
            }))
    
    def _get_user_id_from_connection(self, connection_id: str) -> Optional[int]:
        """从连接ID获取用户ID"""
        # 这需要根据实际的SpectatorHub实现来调整
        for client in self.hub.clients.values():
            if client.connection_id == connection_id:
                return client.user_id
        return None


# 在SpectatorHub类中添加的方法
async def init_multiplayer_integration(self):
    """初始化多人游戏集成"""
    if not hasattr(self, 'multiplayer_integration'):
        self.multiplayer_integration = SpectatorMultiplayerIntegration(self)
        await self.multiplayer_integration.initialize()

async def WatchMultiplayerRoom(self, client, room_id: int):
    """开始观战多人游戏房间"""
    try:
        if not hasattr(self, 'multiplayer_integration'):
            await self.init_multiplayer_integration()
        
        await self.multiplayer_integration.subscribe_to_multiplayer_room(
            client.connection_id, room_id
        )
        
        # 请求当前状态同步
        await self.multiplayer_integration.request_multiplayer_leaderboard(
            client.connection_id, room_id
        )
        
        return {"success": True, "message": f"Now watching multiplayer room {room_id}"}
    except Exception as e:
        logger.error(f"Error starting multiplayer room watch: {e}")
        raise InvokeException(f"Failed to watch multiplayer room: {e}")

async def StopWatchingMultiplayerRoom(self, client, room_id: int):
    """停止观战多人游戏房间"""
    try:
        if hasattr(self, 'multiplayer_integration'):
            await self.multiplayer_integration.unsubscribe_from_multiplayer_room(
                client.connection_id, room_id
            )
        
        return {"success": True, "message": f"Stopped watching multiplayer room {room_id}"}
    except Exception as e:
        logger.error(f"Error stopping multiplayer room watch: {e}")
        raise InvokeException(f"Failed to stop watching multiplayer room: {e}")

async def RequestMultiplayerLeaderboard(self, client, room_id: int):
    """请求多人游戏实时排行榜"""
    try:
        if not hasattr(self, 'multiplayer_integration'):
            await self.init_multiplayer_integration()
        
        await self.multiplayer_integration.request_multiplayer_leaderboard(
            client.connection_id, room_id
        )
        
        return {"success": True, "message": "Leaderboard request sent"}
    except Exception as e:
        logger.error(f"Error requesting multiplayer leaderboard: {e}")
        raise InvokeException(f"Failed to request leaderboard: {e}")
