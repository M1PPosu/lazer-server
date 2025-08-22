"""
观战缓冲区测试脚本
用于验证观战同步和缓冲区功能是否正常工作
"""

import asyncio
import json
from datetime import UTC, datetime

from app.signalr.hub.spectator_buffer import SpectatorStateManager, spectator_state_manager
from app.models.spectator_hub import SpectatorState, SpectatedUserState

async def test_spectator_buffer():
    """测试观战缓冲区功能"""
    print("=== 观战缓冲区测试开始 ===")
    
    # 模拟用户1开始游戏
    user1_id = 100
    user1_state = SpectatorState(
        beatmap_id=123456,
        ruleset_id=0,
        mods=[],
        state=SpectatedUserState.Playing,
        maximum_statistics={}
    )
    
    await spectator_state_manager.handle_user_began_playing(user1_id, user1_state, {
        'beatmap_checksum': 'test_checksum',
        'score_token': 12345,
        'username': 'TestUser1',
        'started_at': datetime.now(UTC).timestamp()
    })
    print(f"✓ 用户 {user1_id} 开始游戏 (谱面: {user1_state.beatmap_id})")
    
    # 模拟多人游戏同步
    multiplayer_data = {
        'room_id': 10,
        'beatmap_id': 789012,  # 不同的谱面ID
        'ruleset_id': 1,       # 不同的模式
        'mods': [],
        'state': 'PLAYING',
        'is_multiplayer': True
    }
    
    user2_id = 200
    await spectator_state_manager.sync_with_multiplayer(user2_id, multiplayer_data)
    print(f"✓ 用户 {user2_id} 多人游戏同步 (谱面: {multiplayer_data['beatmap_id']}, 模式: {multiplayer_data['ruleset_id']})")
    
    # 模拟观战者开始观看
    spectator_id = 300
    catchup_bundle = await spectator_state_manager.handle_spectator_start_watching(spectator_id, user1_id)
    print(f"✓ 观战者 {spectator_id} 开始观看用户 {user1_id}")
    
    if catchup_bundle:
        print(f"  - 追赶数据包包含: {list(catchup_bundle.keys())}")
        if 'state' in catchup_bundle:
            state = catchup_bundle['state']
            print(f"  - 谱面ID: {state.beatmap_id}, 模式: {state.ruleset_id}")
    
    # 检查缓冲区统计
    stats = spectator_state_manager.get_buffer_stats()
    print(f"✓ 缓冲区统计: {stats}")
    
    # 验证状态同步
    user1_buffered = spectator_state_manager.buffer.get_user_state(user1_id)
    user2_buffered = spectator_state_manager.buffer.get_user_state(user2_id)
    
    if user1_buffered:
        print(f"✓ 用户1缓冲状态: 谱面={user1_buffered.beatmap_id}, 模式={user1_buffered.ruleset_id}")
    
    if user2_buffered:
        print(f"✓ 用户2缓冲状态: 谱面={user2_buffered.beatmap_id}, 模式={user2_buffered.ruleset_id}")
    
    # 验证不同谱面的处理
    if user1_buffered and user2_buffered:
        if user1_buffered.beatmap_id != user2_buffered.beatmap_id:
            print("✓ 不同用户的不同谱面已正确处理")
        else:
            print("⚠️ 用户谱面同步可能存在问题")
    
    print("=== 观战缓冲区测试完成 ===")

if __name__ == "__main__":
    asyncio.run(test_spectator_buffer())
