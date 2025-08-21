#!/usr/bin/env python3
"""
服务器统计API测试脚本
"""

import asyncio
import json
from datetime import datetime

import httpx


async def test_stats_api():
    """测试统计API"""
    base_url = "http://localhost:8000"  # 根据实际服务器地址修改
    
    async with httpx.AsyncClient() as client:
        print("🧪 测试服务器统计API...")
        
        # 测试服务器统计信息接口
        print("\n1. 测试 /api/v2/stats 端点...")
        try:
            response = await client.get(f"{base_url}/api/v2/stats")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ 成功获取服务器统计信息:")
                print(f"   - 注册用户: {data['registered_users']}")
                print(f"   - 在线用户: {data['online_users']}")  
                print(f"   - 游玩用户: {data['playing_users']}")
                print(f"   - 更新时间: {data['timestamp']}")
            else:
                print(f"❌ 请求失败: HTTP {response.status_code}")
                print(f"   响应: {response.text}")
        except Exception as e:
            print(f"❌ 请求异常: {e}")
        
        # 测试在线历史接口
        print("\n2. 测试 /api/v2/stats/history 端点...")
        try:
            response = await client.get(f"{base_url}/api/v2/stats/history")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ 成功获取在线历史信息:")
                print(f"   - 历史数据点数: {len(data['history'])}")
                print(f"   - 当前统计信息:")
                current = data['current_stats']
                print(f"     - 注册用户: {current['registered_users']}")
                print(f"     - 在线用户: {current['online_users']}")
                print(f"     - 游玩用户: {current['playing_users']}")
                
                if data['history']:
                    latest = data['history'][0]
                    print(f"   - 最新历史记录:")
                    print(f"     - 时间: {latest['timestamp']}")
                    print(f"     - 在线数: {latest['online_count']}")
                    print(f"     - 游玩数: {latest['playing_count']}")
                else:
                    print(f"   - 暂无历史数据（需要等待调度器记录）")
            else:
                print(f"❌ 请求失败: HTTP {response.status_code}")
                print(f"   响应: {response.text}")
        except Exception as e:
            print(f"❌ 请求异常: {e}")


async def test_internal_functions():
    """测试内部函数"""
    print("\n🔧 测试内部Redis函数...")
    
    try:
        from app.router.v2.stats import (
            add_online_user, 
            remove_online_user,
            add_playing_user, 
            remove_playing_user,
            record_hourly_stats,
            update_registered_users_count
        )
        
        # 测试添加用户
        print("   测试添加在线用户...")
        await add_online_user(999999)  # 测试用户ID
        
        print("   测试添加游玩用户...")
        await add_playing_user(999999)
        
        print("   测试记录统计数据...")
        await record_hourly_stats()
        
        print("   测试移除用户...")
        await remove_playing_user(999999)
        await remove_online_user(999999)
        
        print("   测试更新注册用户数...")
        await update_registered_users_count()
        
        print("✅ 内部函数测试完成")
        
    except Exception as e:
        print(f"❌ 内部函数测试异常: {e}")


if __name__ == "__main__":
    print("🚀 开始测试服务器统计功能...")
    
    # 首先测试内部函数
    asyncio.run(test_internal_functions())
    
    # 然后测试API端点
    asyncio.run(test_stats_api())
    
    print("\n✨ 测试完成!")
