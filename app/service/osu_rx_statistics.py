from __future__ import annotations

from app.config import settings
from app.database.lazer_user import User
from app.database.statistics import UserStatistics
from app.dependencies.database import engine
from app.models.score import GameMode

from sqlalchemy import exists
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession


async def create_rx_statistics():
    async with AsyncSession(engine) as session:
        users = (await session.exec(select(User.id))).all()
        for i in users:
            if settings.enable_osu_rx:
                is_exist = (
                    await session.exec(
                        select(exists()).where(
                            UserStatistics.user_id == i,
                            UserStatistics.mode == GameMode.OSURX,
                        )
                    )
                ).first()
                if not is_exist:
                    statistics_rx = UserStatistics(mode=GameMode.OSURX, user_id=i)
                    session.add(statistics_rx)
            if settings.enable_osu_ap:
                is_exist = (
                    await session.exec(
                        select(exists()).where(
                            UserStatistics.user_id == i,
                            UserStatistics.mode == GameMode.OSUAP,
                        )
                    )
                ).first()
                if not is_exist:
                    statistics_ap = UserStatistics(mode=GameMode.OSUAP, user_id=i)
                    session.add(statistics_ap)
        await session.commit()
