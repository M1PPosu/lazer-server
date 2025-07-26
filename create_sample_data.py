#!/usr/bin/env python3
"""
osu! API 模拟服务器的示例数据填充脚本
"""

from __future__ import annotations

import asyncio
from datetime import datetime

from app.auth import get_password_hash
from app.database import (
    User,
)
from app.database.beatmapset import Beatmapset, BeatmapsetResp
from app.database.beatmap import Beatmap, BeatmapResp
from app.database.score import Score
from app.models.score import GameMode, Rank, APIMod
from app.models.beatmap import BeatmapRankStatus, Genre, Language
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
            # current_timestamp = int(time.time())
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


async def create_sample_beatmap_data(user: User):
    """创建示例谱面数据"""
    async with AsyncSession(engine) as session:
        async with session.begin():
            # 检查谱面集是否已存在
            statement = select(Beatmapset).where(Beatmapset.id == 1)
            result = await session.execute(statement)
            existing_beatmapset = result.scalars().first()
            if existing_beatmapset:
                print("示例谱面集已存在，跳过创建")
                return existing_beatmapset

            # 创建谱面集
            beatmapset = Beatmapset(
                id=1,
                artist="Example Artist",
                artist_unicode="Example Artist",
                covers=None,
                creator="Googujiang",
                favourite_count=0,
                hype_current=0,
                hype_required=0,
                nsfw=False,
                play_count=0,
                preview_url="",
                source="",
                spotlight=False,
                title="Example Song",
                title_unicode="Example Song",
                user_id=user.id,
                video=False,
                availability_info=None,
                download_disabled=False,
                bpm=180.0,
                can_be_hyped=False,
                discussion_locked=False,
                last_updated=datetime.now(),
                ranked_date=datetime.now(),
                storyboard=False,
                submitted_date=datetime.now(),
                current_nominations=[],
                beatmap_status=BeatmapRankStatus.RANKED,
                beatmap_genre=Genre.ANY,  # 使用整数表示Genre枚举
                beatmap_language=Language.ANY,  # 使用整数表示Language枚举
                nominations_required=0,
                nominations_current=0,
                pack_tags=[],
                ratings=[],
            )
            session.add(beatmapset)
            await session.flush()

            # 创建谱面
            beatmap = Beatmap(
                id=1,
                url="",
                mode=GameMode.OSU,
                beatmapset_id=1,
                difficulty_rating=5.5,
                beatmap_status=BeatmapRankStatus.RANKED,
                total_length=195,
                user_id=user.id,
                version="Example Difficulty",
                checksum="example_checksum",
                current_user_playcount=0,
                max_combo=1200,
                ar=9.0,
                cs=4.0,
                drain=5.0,
                accuracy=8.0,
                bpm=180.0,
                count_circles=1000,
                count_sliders=200,
                count_spinners=1,
                deleted_at=None,
                hit_length=180,
                last_updated=datetime.now(),
                passcount=10,
                playcount=50,
            )
            session.add(beatmap)
            await session.flush()

            # 创建成绩
            score = Score(
                id=1,
                accuracy=0.9876,
                map_md5="example_checksum",
                best_id=1,
                build_id=None,
                classic_total_score=1234567,
                ended_at=datetime.now(),
                has_replay=True,
                max_combo=1100,
                mods=[APIMod(acronym="HD"), APIMod(acronym="DT")],
                passed=True,
                playlist_item_id=None,
                pp=250.5,
                preserve=True,
                rank=Rank.S,
                room_id=None,
                ruleset_id=GameMode.OSU,
                started_at=datetime.now(),
                total_score=1234567,
                type="solo_score",
                position=None,
                beatmap_id=1,
                user_id=user.id,
                n300=950,
                n100=30,
                n50=20,
                nmiss=5,
                ngeki=150,
                nkatu=50,
                nlarge_tick_miss=None,
                nslider_tail_hit=None,
            )
            session.add(score)
            await session.commit()
            await session.refresh(beatmapset)

            print(f"成功创建示例谱面集: {beatmapset.title} (ID: {beatmapset.id})")
            print(f"成功创建示例谱面: {beatmap.version} (ID: {beatmap.id})")
            print(f"成功创建示例成绩: ID {score.id}")
            return beatmapset


async def main():
    print("开始创建示例数据...")
    await create_tables()
    user = await create_sample_user()
    await create_sample_beatmap_data(user)
    print("示例数据创建完成！")
    print(f"用户名: {user.name}")
    print("密码: password123")
    print("现在您可以使用这些凭据来测试API了。")


if __name__ == "__main__":
    asyncio.run(main())