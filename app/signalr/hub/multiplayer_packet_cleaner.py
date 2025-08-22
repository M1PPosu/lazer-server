"""
多人游戏数据包清理管理器
基于osu-server源码实现的数据包清理逻辑
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Dict, List, Optional, Set
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class MultiplayerPacketCleaner:
    """多人游戏数据包清理管理器（基于osu源码设计）"""
    
    def __init__(self):
        # 待清理的数据包队列
        self.cleanup_queue: Dict[int, List[Dict]] = defaultdict(list)
        # 清理任务映射
        self.cleanup_tasks: Dict[int, asyncio.Task] = {}
        # 延迟清理时间（秒）
        self.cleanup_delay = 5.0
        # 强制清理时间（秒）
        self.force_cleanup_delay = 30.0
    
    async def schedule_cleanup(self, room_id: int, packet_data: Dict):
        """安排数据包清理（参考osu源码的清理调度）"""
        self.cleanup_queue[room_id].append({
            **packet_data,
            'scheduled_at': datetime.now(UTC),
            'room_id': room_id
        })
        
        # 如果没有正在进行的清理任务，开始新的清理任务
        if room_id not in self.cleanup_tasks or self.cleanup_tasks[room_id].done():
            self.cleanup_tasks[room_id] = asyncio.create_task(
                self._delayed_cleanup_task(room_id)
            )
            logger.debug(f"[PacketCleaner] Scheduled cleanup task for room {room_id}")
    
    async def _delayed_cleanup_task(self, room_id: int):
        """延迟清理任务（类似osu源码的延迟清理机制）"""
        try:
            # 等待延迟时间
            await asyncio.sleep(self.cleanup_delay)
            
            # 执行清理
            await self._execute_cleanup(room_id)
            
        except asyncio.CancelledError:
            logger.debug(f"[PacketCleaner] Cleanup task for room {room_id} was cancelled")
            raise
        except Exception as e:
            logger.error(f"[PacketCleaner] Error during cleanup for room {room_id}: {e}")
    
    async def _execute_cleanup(self, room_id: int):
        """执行实际的清理操作"""
        if room_id not in self.cleanup_queue:
            return
            
        packets_to_clean = self.cleanup_queue.pop(room_id, [])
        if not packets_to_clean:
            return
        
        logger.info(f"[PacketCleaner] Cleaning {len(packets_to_clean)} packets for room {room_id}")
        
        # 按类型分组处理清理
        score_packets = []
        state_packets = []
        leaderboard_packets = []
        
        for packet in packets_to_clean:
            packet_type = packet.get('type', 'unknown')
            if packet_type == 'score':
                score_packets.append(packet)
            elif packet_type == 'state':
                state_packets.append(packet)
            elif packet_type == 'leaderboard':
                leaderboard_packets.append(packet)
        
        # 清理分数数据包
        if score_packets:
            await self._cleanup_score_packets(room_id, score_packets)
        
        # 清理状态数据包
        if state_packets:
            await self._cleanup_state_packets(room_id, state_packets)
            
        # 清理排行榜数据包
        if leaderboard_packets:
            await self._cleanup_leaderboard_packets(room_id, leaderboard_packets)
    
    async def _cleanup_score_packets(self, room_id: int, packets: List[Dict]):
        """清理分数相关数据包"""
        user_ids = set(p.get('user_id') for p in packets if p.get('user_id'))
        logger.debug(f"[PacketCleaner] Cleaning score packets for {len(user_ids)} users in room {room_id}")
        
        # 这里可以添加具体的清理逻辑，比如：
        # - 清理过期的分数帧
        # - 压缩历史分数数据
        # - 清理缓存
    
    async def _cleanup_state_packets(self, room_id: int, packets: List[Dict]):
        """清理状态相关数据包"""
        logger.debug(f"[PacketCleaner] Cleaning {len(packets)} state packets for room {room_id}")
        
        # 这里可以添加状态清理逻辑，比如：
        # - 清理过期状态数据
        # - 重置用户状态缓存
    
    async def _cleanup_leaderboard_packets(self, room_id: int, packets: List[Dict]):
        """清理排行榜相关数据包"""
        logger.debug(f"[PacketCleaner] Cleaning {len(packets)} leaderboard packets for room {room_id}")
        
        # 这里可以添加排行榜清理逻辑
    
    async def force_cleanup(self, room_id: int):
        """强制立即清理指定房间的数据包"""
        # 取消延迟清理任务
        if room_id in self.cleanup_tasks:
            task = self.cleanup_tasks.pop(room_id)
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        # 立即执行清理
        await self._execute_cleanup(room_id)
        logger.info(f"[PacketCleaner] Force cleaned packets for room {room_id}")
    
    async def cleanup_all_for_room(self, room_id: int):
        """清理房间的所有数据包（房间结束时调用）"""
        await self.force_cleanup(room_id)
        
        # 清理任务引用
        self.cleanup_tasks.pop(room_id, None)
        self.cleanup_queue.pop(room_id, None)
        
        logger.info(f"[PacketCleaner] Completed full cleanup for room {room_id}")
    
    async def cleanup_expired_packets(self):
        """定期清理过期的数据包"""
        current_time = datetime.now(UTC)
        expired_rooms = []
        
        for room_id, packets in self.cleanup_queue.items():
            # 查找超过强制清理时间的数据包
            expired_packets = [
                p for p in packets
                if (current_time - p['scheduled_at']).total_seconds() > self.force_cleanup_delay
            ]
            
            if expired_packets:
                expired_rooms.append(room_id)
        
        # 强制清理过期数据包
        for room_id in expired_rooms:
            await self.force_cleanup(room_id)
    
    def get_cleanup_stats(self) -> Dict:
        """获取清理统计信息"""
        return {
            'active_cleanup_tasks': len([t for t in self.cleanup_tasks.values() if not t.done()]),
            'pending_packets': sum(len(packets) for packets in self.cleanup_queue.values()),
            'rooms_with_pending_cleanup': len(self.cleanup_queue),
        }


# 全局实例
packet_cleaner = MultiplayerPacketCleaner()


class GameSessionCleaner:
    """游戏会话清理器（参考osu源码的会话管理）"""
    
    @staticmethod
    async def cleanup_game_session(room_id: int, game_completed: bool = False):
        """清理游戏会话数据（每局游戏结束后调用）"""
        try:
            # 安排数据包清理
            await packet_cleaner.schedule_cleanup(room_id, {
                'type': 'game_session_end',
                'completed': game_completed,
                'timestamp': datetime.now(UTC).isoformat()
            })
            
            logger.info(f"[GameSessionCleaner] Scheduled cleanup for game session in room {room_id} (completed: {game_completed})")
            
        except Exception as e:
            logger.error(f"[GameSessionCleaner] Failed to cleanup game session for room {room_id}: {e}")
    
    @staticmethod
    async def cleanup_user_session(room_id: int, user_id: int):
        """清理单个用户的会话数据"""
        try:
            await packet_cleaner.schedule_cleanup(room_id, {
                'type': 'user_session_end',
                'user_id': user_id,
                'timestamp': datetime.now(UTC).isoformat()
            })
            
            logger.debug(f"[GameSessionCleaner] Scheduled cleanup for user {user_id} in room {room_id}")
            
        except Exception as e:
            logger.error(f"[GameSessionCleaner] Failed to cleanup user session {user_id} in room {room_id}: {e}")
    
    @staticmethod
    async def cleanup_room_fully(room_id: int):
        """完全清理房间数据（房间关闭时调用）"""
        try:
            await packet_cleaner.cleanup_all_for_room(room_id)
            logger.info(f"[GameSessionCleaner] Completed full room cleanup for {room_id}")
            
        except Exception as e:
            logger.error(f"[GameSessionCleaner] Failed to fully cleanup room {room_id}: {e}")
