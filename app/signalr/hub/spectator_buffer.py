"""
观战Hub缓冲区管理器
解决第一局游戏结束后观战和排行榜不同步的问题
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Dict, List, Optional, Tuple, Set
from collections import defaultdict, deque
import logging

from app.models.spectator_hub import SpectatorState, FrameDataBundle, SpectatedUserState
from app.models.multiplayer_hub import MultiplayerUserState

logger = logging.getLogger(__name__)


class SpectatorBuffer:
    """观战数据缓冲区，解决观战状态不同步问题"""
    
    def __init__(self):
        # 用户ID -> 游戏状态缓存
        self.user_states: Dict[int, SpectatorState] = {}
        
        # 用户ID -> 帧数据缓冲区 (保留最近的帧数据)
        self.frame_buffers: Dict[int, deque] = defaultdict(lambda: deque(maxlen=30))
        
        # 用户ID -> 最后活跃时间
        self.last_activity: Dict[int, datetime] = {}
        
        # 用户ID -> 观战者列表
        self.spectators: Dict[int, Set[int]] = defaultdict(set)
        
        # 用户ID -> 游戏会话信息
        self.session_info: Dict[int, Dict] = {}
        
        # 多人游戏同步缓存
        self.multiplayer_sync_cache: Dict[int, Dict] = {}  # user_id -> multiplayer_data
        
        # 缓冲区过期时间（分钟）
        self.buffer_expire_time = 10
        
    def update_user_state(self, user_id: int, state: SpectatorState, session_data: Optional[Dict] = None):
        """更新用户状态到缓冲区"""
        self.user_states[user_id] = state
        self.last_activity[user_id] = datetime.now(UTC)
        
        if session_data:
            self.session_info[user_id] = session_data
            
        logger.debug(f"[SpectatorBuffer] Updated state for user {user_id}: {state.state}")
    
    def add_frame_data(self, user_id: int, frame_data: FrameDataBundle):
        """添加帧数据到缓冲区"""
        self.frame_buffers[user_id].append({
            'data': frame_data,
            'timestamp': datetime.now(UTC)
        })
        self.last_activity[user_id] = datetime.now(UTC)
        
    def get_user_state(self, user_id: int) -> Optional[SpectatorState]:
        """获取用户当前状态"""
        return self.user_states.get(user_id)
    
    def get_recent_frames(self, user_id: int, count: int = 10) -> List[FrameDataBundle]:
        """获取用户最近的帧数据"""
        frames = self.frame_buffers.get(user_id, deque())
        recent_frames = list(frames)[-count:] if len(frames) >= count else list(frames)
        return [frame['data'] for frame in recent_frames]
    
    def add_spectator(self, user_id: int, spectator_id: int):
        """添加观战者"""
        self.spectators[user_id].add(spectator_id)
        logger.debug(f"[SpectatorBuffer] Added spectator {spectator_id} to user {user_id}")
    
    def remove_spectator(self, user_id: int, spectator_id: int):
        """移除观战者"""
        self.spectators[user_id].discard(spectator_id)
        logger.debug(f"[SpectatorBuffer] Removed spectator {spectator_id} from user {user_id}")
    
    def get_spectators(self, user_id: int) -> Set[int]:
        """获取用户的所有观战者"""
        return self.spectators.get(user_id, set())
    
    def clear_user_data(self, user_id: int):
        """清理用户数据（游戏结束时调用，但保留一段时间用于观战同步）"""
        # 不立即删除，而是标记为已结束，延迟清理
        if user_id in self.user_states:
            current_state = self.user_states[user_id]
            if current_state.state == SpectatedUserState.Playing:
                # 将状态标记为已结束，但保留在缓冲区中
                current_state.state = SpectatedUserState.Passed  # 或其他结束状态
                self.user_states[user_id] = current_state
                logger.debug(f"[SpectatorBuffer] Marked user {user_id} as finished, keeping in buffer")
    
    def cleanup_expired_data(self):
        """清理过期数据"""
        current_time = datetime.now(UTC)
        expired_users = []
        
        for user_id, last_time in self.last_activity.items():
            if (current_time - last_time).total_seconds() > self.buffer_expire_time * 60:
                expired_users.append(user_id)
        
        for user_id in expired_users:
            self._force_clear_user(user_id)
            logger.debug(f"[SpectatorBuffer] Cleaned expired data for user {user_id}")
    
    def _force_clear_user(self, user_id: int):
        """强制清理用户数据"""
        self.user_states.pop(user_id, None)
        self.frame_buffers.pop(user_id, None)
        self.last_activity.pop(user_id, None)
        self.spectators.pop(user_id, None)
        self.session_info.pop(user_id, None)
        self.multiplayer_sync_cache.pop(user_id, None)
    
    def sync_multiplayer_state(self, user_id: int, multiplayer_data: Dict):
        """同步多人游戏状态"""
        self.multiplayer_sync_cache[user_id] = {
            **multiplayer_data,
            'synced_at': datetime.now(UTC)
        }
        logger.debug(f"[SpectatorBuffer] Synced multiplayer state for user {user_id}")
    
    def get_multiplayer_sync_data(self, user_id: int) -> Optional[Dict]:
        """获取多人游戏同步数据"""
        return self.multiplayer_sync_cache.get(user_id)
    
    def has_active_spectators(self, user_id: int) -> bool:
        """检查用户是否有活跃的观战者"""
        return len(self.spectators.get(user_id, set())) > 0
    
    def get_all_active_users(self) -> List[int]:
        """获取所有活跃用户"""
        current_time = datetime.now(UTC)
        active_users = []
        
        for user_id, last_time in self.last_activity.items():
            if (current_time - last_time).total_seconds() < 300:  # 5分钟内活跃
                active_users.append(user_id)
        
        return active_users
    
    def create_catchup_bundle(self, user_id: int) -> Optional[Dict]:
        """为新观战者创建追赶数据包"""
        if user_id not in self.user_states:
            return None
            
        state = self.user_states[user_id]
        recent_frames = self.get_recent_frames(user_id, 20)  # 获取最近20帧
        session_data = self.session_info.get(user_id, {})
        
        return {
            'user_id': user_id,
            'state': state,
            'recent_frames': recent_frames,
            'session_info': session_data,
            'multiplayer_data': self.get_multiplayer_sync_data(user_id),
            'created_at': datetime.now(UTC).isoformat()
        }
    
    def get_buffer_stats(self) -> Dict:
        """获取缓冲区统计信息"""
        return {
            'active_users': len(self.user_states),
            'total_spectators': sum(len(specs) for specs in self.spectators.values()),
            'buffered_frames': sum(len(frames) for frames in self.frame_buffers.values()),
            'multiplayer_synced_users': len(self.multiplayer_sync_cache)
        }


class SpectatorStateManager:
    """观战状态管理器，处理状态同步和缓冲"""
    
    def __init__(self):
        self.buffer = SpectatorBuffer()
        self.cleanup_task: Optional[asyncio.Task] = None
        self.start_cleanup_task()
    
    def start_cleanup_task(self):
        """启动定期清理任务"""
        if self.cleanup_task is None or self.cleanup_task.done():
            self.cleanup_task = asyncio.create_task(self._periodic_cleanup())
    
    async def _periodic_cleanup(self):
        """定期清理过期数据"""
        while True:
            try:
                await asyncio.sleep(300)  # 每5分钟清理一次
                self.buffer.cleanup_expired_data()
                
                stats = self.buffer.get_buffer_stats()
                if stats['active_users'] > 0:
                    logger.debug(f"[SpectatorStateManager] Buffer stats: {stats}")
                    
            except Exception as e:
                logger.error(f"[SpectatorStateManager] Error in periodic cleanup: {e}")
            except asyncio.CancelledError:
                logger.info("[SpectatorStateManager] Periodic cleanup task cancelled")
                break
    
    async def handle_user_began_playing(self, user_id: int, state: SpectatorState, session_data: Optional[Dict] = None):
        """处理用户开始游戏"""
        self.buffer.update_user_state(user_id, state, session_data)
        
        # 如果有观战者，发送追赶数据
        spectators = self.buffer.get_spectators(user_id)
        if spectators:
            logger.debug(f"[SpectatorStateManager] User {user_id} has {len(spectators)} spectators, maintaining buffer")
    
    async def handle_user_finished_playing(self, user_id: int, final_state: SpectatorState):
        """处理用户结束游戏"""
        # 更新为结束状态，但保留在缓冲区中以便观战者同步
        self.buffer.update_user_state(user_id, final_state)
        
        # 如果有观战者，保持数据在缓冲区中更长时间
        if self.buffer.has_active_spectators(user_id):
            logger.debug(f"[SpectatorStateManager] User {user_id} finished, keeping data for spectators")
        else:
            # 延迟清理
            asyncio.create_task(self._delayed_cleanup_user(user_id, 60))  # 60秒后清理
    
    async def _delayed_cleanup_user(self, user_id: int, delay_seconds: int):
        """延迟清理用户数据"""
        await asyncio.sleep(delay_seconds)
        if not self.buffer.has_active_spectators(user_id):
            self.buffer.clear_user_data(user_id)
            logger.debug(f"[SpectatorStateManager] Delayed cleanup for user {user_id}")
    
    async def handle_frame_data(self, user_id: int, frame_data: FrameDataBundle):
        """处理帧数据"""
        self.buffer.add_frame_data(user_id, frame_data)
    
    async def handle_spectator_start_watching(self, spectator_id: int, target_id: int) -> Optional[Dict]:
        """处理观战者开始观看，返回追赶数据包"""
        self.buffer.add_spectator(target_id, spectator_id)
        
        # 为新观战者创建追赶数据包
        catchup_bundle = self.buffer.create_catchup_bundle(target_id)
        
        if catchup_bundle:
            logger.debug(f"[SpectatorStateManager] Created catchup bundle for spectator {spectator_id} watching {target_id}")
        
        return catchup_bundle
    
    async def handle_spectator_stop_watching(self, spectator_id: int, target_id: int):
        """处理观战者停止观看"""
        self.buffer.remove_spectator(target_id, spectator_id)
    
    async def sync_with_multiplayer(self, user_id: int, multiplayer_data: Dict):
        """与多人游戏模式同步"""
        self.buffer.sync_multiplayer_state(user_id, multiplayer_data)
        
        beatmap_id = multiplayer_data.get('beatmap_id')
        ruleset_id = multiplayer_data.get('ruleset_id', 0)
        
        logger.info(
            f"[SpectatorStateManager] Syncing multiplayer data for user {user_id}: "
            f"beatmap={beatmap_id}, ruleset={ruleset_id}"
        )
        
        # 如果用户没有在SpectatorHub中但在多人游戏中，创建同步状态
        if user_id not in self.buffer.user_states:
            try:
                synthetic_state = SpectatorState(
                    beatmap_id=beatmap_id,
                    ruleset_id=ruleset_id,
                    mods=multiplayer_data.get('mods', []),
                    state=self._convert_multiplayer_state(multiplayer_data.get('state')),
                    maximum_statistics=multiplayer_data.get('maximum_statistics', {}),
                )
                
                await self.handle_user_began_playing(user_id, synthetic_state, {
                    'source': 'multiplayer',
                    'room_id': multiplayer_data.get('room_id'),
                    'beatmap_id': beatmap_id,
                    'ruleset_id': ruleset_id,
                    'is_multiplayer': multiplayer_data.get('is_multiplayer', True),
                    'synced_at': datetime.now(UTC).isoformat()
                })
                
                logger.info(
                    f"[SpectatorStateManager] Created synthetic state for multiplayer user {user_id} "
                    f"(beatmap: {beatmap_id}, ruleset: {ruleset_id})"
                )
                
            except Exception as e:
                logger.error(f"[SpectatorStateManager] Failed to create synthetic state for user {user_id}: {e}")
        else:
            # 更新现有状态
            existing_state = self.buffer.user_states[user_id]
            if existing_state.beatmap_id != beatmap_id or existing_state.ruleset_id != ruleset_id:
                logger.info(
                    f"[SpectatorStateManager] Updating state for user {user_id}: "
                    f"beatmap {existing_state.beatmap_id} -> {beatmap_id}, "
                    f"ruleset {existing_state.ruleset_id} -> {ruleset_id}"
                )
                
                # 更新状态以匹配多人游戏
                existing_state.beatmap_id = beatmap_id
                existing_state.ruleset_id = ruleset_id
                existing_state.mods = multiplayer_data.get('mods', [])
                
                self.buffer.update_user_state(user_id, existing_state)
    
    def _convert_multiplayer_state(self, mp_state) -> SpectatedUserState:
        """将多人游戏状态转换为观战状态"""
        if not mp_state:
            return SpectatedUserState.Playing
            
        # 假设mp_state是MultiplayerUserState类型
        if hasattr(mp_state, 'name'):
            state_name = mp_state.name
            if 'PLAYING' in state_name:
                return SpectatedUserState.Playing
            elif 'RESULTS' in state_name:
                return SpectatedUserState.Passed
            elif 'FAILED' in state_name:
                return SpectatedUserState.Failed
            elif 'QUIT' in state_name:
                return SpectatedUserState.Quit
        
        return SpectatedUserState.Playing  # 默认状态
    
    def get_buffer_stats(self) -> Dict:
        """获取缓冲区统计信息"""
        return self.buffer.get_buffer_stats()
    
    def stop_cleanup_task(self):
        """停止清理任务"""
        if self.cleanup_task and not self.cleanup_task.done():
            self.cleanup_task.cancel()


# 全局实例
spectator_state_manager = SpectatorStateManager()
