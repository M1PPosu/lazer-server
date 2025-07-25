#!/usr/bin/env python3
"""
Lazer API 系统测试脚本
验证新的 lazer 表支持是否正常工作
"""

from __future__ import annotations

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app.database import User
from app.dependencies.database import engine
from app.utils import convert_db_user_to_api_user

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession


async def test_lazer_tables():
    """测试 lazer 表的基本功能"""
    print("测试 Lazer API 表支持...")

    async with AsyncSession(engine) as session:
        async with session.begin():
            try:
                # 测试查询用户
                statement = select(User)
                result = await session.execute(statement)
                user = result.scalars().first()
                if not user:
                    print("❌ 没有找到用户，请先同步数据")
                    return False

                print(f"✓ 找到用户: {user.name} (ID: {user.id})")

                # 测试 lazer 资料
                if user.lazer_profile:
                    print(
                        f"✓ 用户有 lazer 资料: 支持者={user.lazer_profile.is_supporter}"
                    )
                else:
                    print("⚠ 用户没有 lazer 资料，将使用默认值")

                # 测试 lazer 统计
                osu_stats = None
                for stat in user.lazer_statistics:
                    if stat.mode == "osu":
                        osu_stats = stat
                        break

                if osu_stats:
                    print(
                        f"✓ 用户有 osu! 统计: PP={osu_stats.pp}, "
                        f"游戏次数={osu_stats.play_count}"
                    )
                else:
                    print("⚠ 用户没有 osu! 统计，将使用默认值")

                # 测试转换为 API 格式
                api_user = convert_db_user_to_api_user(user, "osu")
                print("✓ 成功转换为 API 用户格式")
                print(f"  - 用户名: {api_user.username}")
                print(f"  - 国家: {api_user.country_code}")
                print(f"  - PP: {api_user.statistics.pp}")
                print(f"  - 是否支持者: {api_user.is_supporter}")

                return True

            except Exception as e:
                print(f"❌ 测试失败: {e}")
                import traceback

                traceback.print_exc()
                return False


async def test_authentication():
    """测试认证功能"""
    print("\n测试认证功能...")

    async with AsyncSession(engine) as session:
        async with session.begin():
            try:
                # 尝试认证第一个用户
                statement = select(User)
                result = await session.execute(statement)
                user = result.scalars().first()
                if not user:
                    print("❌ 没有用户进行认证测试")
                    return False

                print(f"✓ 测试用户: {user.name}")
                print("⚠ 注意: 实际密码认证需要正确的密码")

                return True

            except Exception as e:
                print(f"❌ 认证测试失败: {e}")
                return False


async def main():
    """主测试函数"""
    print("Lazer API 系统测试")
    print("=" * 40)

    # 测试表连接
    success1 = await test_lazer_tables()

    # 测试认证
    success2 = await test_authentication()

    print("\n" + "=" * 40)
    if success1 and success2:
        print("🎉 所有测试通过!")
        print("\n现在可以:")
        print("1. 启动 API 服务器: python main.py")
        print("2. 测试 OAuth 认证")
        print("3. 调用 /api/v2/me/osu 获取用户信息")
    else:
        print("❌ 测试失败，请检查:")
        print("1. 数据库连接是否正常")
        print("2. 是否已运行数据同步脚本")
        print("3. lazer 表是否正确创建")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
