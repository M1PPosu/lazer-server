#!/usr/bin/env python3
"""
osu! API 模拟服务器的示例数据填充脚本
"""

from __future__ import annotations

import asyncio
from datetime import datetime
import time

from app.auth import get_password_hash
from app.database import (
    User,
)
from app.dependencies.database import create_tables, engine

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession


async def create_sample_user():
    """创建示例用户数据"""
    async with AsyncSession(engine) as session:
        async with session.begin():

            # 检查用户是否已存在
            statement = select(User).where(User.name == "Googujiang")
            result = await session.execute(statement)
            existing_user = result.scalars().first()
            if existing_user:
                print("示例用户已存在，跳过创建")
                return existing_user

            # 当前时间戳
            current_timestamp = int(time.time())
            join_timestamp = int(datetime(2019, 11, 29, 17, 23, 13).timestamp())
            last_visit_timestamp = int(datetime(2025, 7, 18, 16, 31, 29).timestamp())

            # 创建用户
            user = User(
                name="Googujiang",
                safe_name="googujiang",  # 安全用户名（小写）
                email="googujiang@example.com",
                priv=1,  # 默认权限
                pw_bcrypt=get_password_hash("password123"),  # 使用新的哈希方式
                country="JP",
                silence_end=0,
                donor_end=0,
                creation_time=join_timestamp,
                latest_activity=last_visit_timestamp,
                clan_id=0,
                clan_priv=0,
                preferred_mode=0,  # 0 = osu!
                play_style=0,
                custom_badge_name=None,
                custom_badge_icon=None,
                userpage_content="「世界に忘れられた」",
                api_key=None,
            )

            session.add(user)
            await session.commit()
            await session.refresh(user)

            # 确保用户ID存在
            if user.id is None:
                raise ValueError("User ID is None after saving to database")

            print(f"成功创建示例用户: {user.name} (ID: {user.id})")
            print(f"安全用户名: {user.safe_name}")
            print(f"邮箱: {user.email}")
            print(f"国家: {user.country}")
            return user


async def main():
    print("开始创建示例数据...")
    await create_tables()
    user = await create_sample_user()
    print("示例数据创建完成！")
    print(f"用户名: {user.name}")
    print("密码: password123")
    print("现在您可以使用这些凭据来测试API了。")


if __name__ == "__main__":
    asyncio.run(main())
