#!/usr/bin/env python3
"""
osu! API 模拟服务器的示例数据填充脚本
"""

from datetime import datetime, timedelta
import time
from sqlalchemy.orm import Session
from app.dependencies import get_db, engine
from app.database import Base, User, UserStatistics, UserAchievement, DailyChallengeStats, RankHistory
from app.auth import get_password_hash

# 创建所有表
Base.metadata.create_all(bind=engine)

def create_sample_user():
    """创建示例用户数据"""
    db = next(get_db())
    
    # 检查用户是否已存在
    existing_user = db.query(User).filter(User.name == "Googujiang").first()
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
        
        # 兼容性字段
        avatar_url="https://a.ppy.sh/15651670?1732362658.jpeg",
        cover_url="https://assets.ppy.sh/user-profile-covers/15651670/0fc7b77adef39765a570e7f535bc383e5a848850d41a8943f8857984330b8bc6.jpeg",
        has_supported=True,
        interests="「世界に忘れられた」",
        location="咕谷国",
        website="https://gmoe.cc",
        playstyle=["mouse", "keyboard", "tablet"],
        profile_order=["me", "recent_activity", "top_ranks", "medals", "historical", "beatmaps", "kudosu"],
        beatmap_playcounts_count=3306,
        favourite_beatmapset_count=15,
        follower_count=98,
        graveyard_beatmapset_count=7,
        mapping_follower_count=1,
        previous_usernames=["hehejun"],
        monthly_playcounts=[
            {"start_date": "2019-11-01", "count": 43},
            {"start_date": "2020-04-01", "count": 216},
            {"start_date": "2020-05-01", "count": 656},
            {"start_date": "2020-07-01", "count": 158},
            {"start_date": "2020-08-01", "count": 174},
            {"start_date": "2020-10-01", "count": 13},
            {"start_date": "2020-11-01", "count": 52},
            {"start_date": "2020-12-01", "count": 140},
            {"start_date": "2021-01-01", "count": 359},
            {"start_date": "2021-02-01", "count": 452},
            {"start_date": "2021-03-01", "count": 77},
            {"start_date": "2021-04-01", "count": 114},
            {"start_date": "2021-05-01", "count": 270},
            {"start_date": "2021-06-01", "count": 148},
            {"start_date": "2021-07-01", "count": 246},
            {"start_date": "2021-08-01", "count": 56},
            {"start_date": "2021-09-01", "count": 136},
            {"start_date": "2021-10-01", "count": 45},
            {"start_date": "2021-11-01", "count": 98},
            {"start_date": "2021-12-01", "count": 54},
            {"start_date": "2022-01-01", "count": 88},
            {"start_date": "2022-02-01", "count": 45},
            {"start_date": "2022-03-01", "count": 6},
            {"start_date": "2022-04-01", "count": 54},
            {"start_date": "2022-05-01", "count": 105},
            {"start_date": "2022-06-01", "count": 37},
            {"start_date": "2022-07-01", "count": 88},
            {"start_date": "2022-08-01", "count": 7},
            {"start_date": "2022-09-01", "count": 9},
            {"start_date": "2022-10-01", "count": 6},
            {"start_date": "2022-11-01", "count": 2},
            {"start_date": "2022-12-01", "count": 16},
            {"start_date": "2023-01-01", "count": 7},
            {"start_date": "2023-04-01", "count": 16},
            {"start_date": "2023-05-01", "count": 3},
            {"start_date": "2023-06-01", "count": 8},
            {"start_date": "2023-07-01", "count": 23},
            {"start_date": "2023-08-01", "count": 3},
            {"start_date": "2023-09-01", "count": 1},
            {"start_date": "2023-10-01", "count": 25},
            {"start_date": "2023-11-01", "count": 160},
            {"start_date": "2023-12-01", "count": 306},
            {"start_date": "2024-01-01", "count": 735},
            {"start_date": "2024-02-01", "count": 420},
            {"start_date": "2024-03-01", "count": 549},
            {"start_date": "2024-04-01", "count": 466},
            {"start_date": "2024-05-01", "count": 333},
            {"start_date": "2024-06-01", "count": 1126},
            {"start_date": "2024-07-01", "count": 534},
            {"start_date": "2024-08-01", "count": 280},
            {"start_date": "2024-09-01", "count": 116},
            {"start_date": "2024-10-01", "count": 120},
            {"start_date": "2024-11-01", "count": 332},
            {"start_date": "2024-12-01", "count": 243},
            {"start_date": "2025-01-01", "count": 122},
            {"start_date": "2025-02-01", "count": 379},
            {"start_date": "2025-03-01", "count": 278},
            {"start_date": "2025-04-01", "count": 296},
            {"start_date": "2025-05-01", "count": 964},
            {"start_date": "2025-06-01", "count": 821},
            {"start_date": "2025-07-01", "count": 230}
        ]
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # 创建 osu! 模式统计
    osu_stats = UserStatistics(
        user_id=user.id,
        mode="osu",
        count_100=276274,
        count_300=1932068,
        count_50=32776,
        count_miss=111064,
        level_current=97,
        level_progress=96,
        global_rank=298026,
        country_rank=11221,
        pp=2826.26,
        ranked_score=4415081049,
        hit_accuracy=95.7168,
        play_count=12711,
        play_time=836529,
        total_score=12390140370,
        total_hits=2241118,
        maximum_combo=1859,
        replays_watched_by_others=0,
        is_ranked=True,
        grade_ss=14,
        grade_ssh=3,
        grade_s=322,
        grade_sh=11,
        grade_a=757,
        rank_highest=295701,
        rank_highest_updated_at=datetime(2025, 7, 2, 17, 30, 21)
    )
    
    # 创建 taiko 模式统计
    taiko_stats = UserStatistics(
        user_id=user.id,
        mode="taiko",
        count_100=160,
        count_300=154,
        count_50=0,
        count_miss=480,
        level_current=2,
        level_progress=49,
        global_rank=None,
        pp=0,
        ranked_score=0,
        hit_accuracy=0,
        play_count=6,
        play_time=217,
        total_score=79301,
        total_hits=314,
        maximum_combo=0,
        replays_watched_by_others=0,
        is_ranked=False
    )
    
    # 创建 fruits 模式统计
    fruits_stats = UserStatistics(
        user_id=user.id,
        mode="fruits",
        count_100=109,
        count_300=1613,
        count_50=1861,
        count_miss=328,
        level_current=6,
        level_progress=14,
        global_rank=None,
        pp=0,
        ranked_score=343854,
        hit_accuracy=89.4779,
        play_count=19,
        play_time=669,
        total_score=1362651,
        total_hits=3583,
        maximum_combo=75,
        replays_watched_by_others=0,
        is_ranked=False,
        grade_a=1
    )
    
    # 创建 mania 模式统计
    mania_stats = UserStatistics(
        user_id=user.id,
        mode="mania",
        count_100=7867,
        count_300=12104,
        count_50=991,
        count_miss=2951,
        level_current=12,
        level_progress=89,
        global_rank=660670,
        pp=25.3784,
        ranked_score=3812295,
        hit_accuracy=77.9316,
        play_count=85,
        play_time=4834,
        total_score=13454470,
        total_hits=20962,
        maximum_combo=573,
        replays_watched_by_others=0,
        is_ranked=True,
        grade_a=1
    )
    
    db.add_all([osu_stats, taiko_stats, fruits_stats, mania_stats])
    
    # 创建每日挑战统计
    daily_challenge = DailyChallengeStats(
        user_id=user.id,
        daily_streak_best=1,
        daily_streak_current=0,
        last_update=datetime(2025, 6, 21, 0, 0, 0),
        last_weekly_streak=datetime(2025, 6, 19, 0, 0, 0),
        playcount=1,
        top_10p_placements=0,
        top_50p_placements=0,
        weekly_streak_best=1,
        weekly_streak_current=0
    )
    
    db.add(daily_challenge)
    
    # 创建排名历史 (最近90天的数据)
    rank_data = [322806, 323092, 323341, 323616, 323853, 324106, 324378, 324676, 324958, 325254, 325492, 325780, 326075, 326356, 326586, 326845, 327067, 327286, 327526, 327778, 328039, 328347, 328631, 328858, 329323, 329557, 329809, 329911, 330188, 330425, 330650, 330881, 331068, 331325, 331575, 331816, 332061, 328959, 315648, 315881, 308784, 309023, 309252, 309433, 309537, 309364, 309548, 308957, 309182, 309426, 309607, 309831, 310054, 310269, 310485, 310714, 310956, 310924, 311125, 311203, 311422, 311640, 303091, 303309, 303500, 303691, 303758, 303750, 303957, 299867, 300088, 300273, 300457, 295799, 295976, 296153, 296350, 296566, 296756, 296933, 297141, 297314, 297480, 297114, 297296, 297480, 297645, 297815, 297993, 298026]
    
    rank_history = RankHistory(
        user_id=user.id,
        mode="osu",
        rank_data=rank_data
    )
    
    db.add(rank_history)
    
    # 创建一些成就
    achievements = [
        UserAchievement(user_id=user.id, achievement_id=336, achieved_at=datetime(2025, 6, 21, 19, 6, 32)),
        UserAchievement(user_id=user.id, achievement_id=319, achieved_at=datetime(2025, 6, 1, 0, 52, 0)),
        UserAchievement(user_id=user.id, achievement_id=222, achieved_at=datetime(2025, 5, 28, 12, 24, 37)),
        UserAchievement(user_id=user.id, achievement_id=38, achieved_at=datetime(2024, 7, 5, 15, 43, 23)),
        UserAchievement(user_id=user.id, achievement_id=67, achieved_at=datetime(2024, 6, 24, 5, 6, 44)),
    ]
    
    db.add_all(achievements)
    
    db.commit()
    print(f"成功创建示例用户: {user.name} (ID: {user.id})")
    print(f"安全用户名: {user.safe_name}")
    print(f"邮箱: {user.email}")
    print(f"国家: {user.country}")
    return user


if __name__ == "__main__":
    print("开始创建示例数据...")
    user = create_sample_user()
    print("示例数据创建完成！")
    print(f"用户名: {user.name}")
    print(f"密码: password123")
    print("现在您可以使用这些凭据来测试API了。")
