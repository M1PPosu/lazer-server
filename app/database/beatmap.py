import asyncio
from datetime import datetime
import hashlib
from typing import TYPE_CHECKING

from app.config import settings
from app.models.beatmap import BeatmapAttributes, BeatmapRankStatus
from app.models.mods import APIMod
from app.models.score import GameMode

from .beatmap_playcounts import BeatmapPlaycounts
from .beatmapset import Beatmapset, BeatmapsetResp

from redis.asyncio import Redis
from sqlalchemy import Column, DateTime
from sqlmodel import VARCHAR, Field, Relationship, SQLModel, col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

if TYPE_CHECKING:
    from app.fetcher import Fetcher

    from .lazer_user import User


class BeatmapOwner(SQLModel):
    id: int
    username: str


class BeatmapBase(SQLModel):
    # Beatmap
    url: str
    mode: GameMode
    beatmapset_id: int = Field(foreign_key="beatmapsets.id", index=True)
    difficulty_rating: float = Field(default=0.0, index=True)
    total_length: int
    user_id: int = Field(index=True)
    version: str = Field(index=True)

    # optional
    checksum: str = Field(sa_column=Column(VARCHAR(32), index=True))
    current_user_playcount: int = Field(default=0)
    max_combo: int | None = Field(default=0)
    # TODO: failtimes, owners

    # BeatmapExtended
    ar: float = Field(default=0.0)
    cs: float = Field(default=0.0)
    drain: float = Field(default=0.0)  # hp
    accuracy: float = Field(default=0.0)  # od
    bpm: float = Field(default=0.0)
    count_circles: int = Field(default=0)
    count_sliders: int = Field(default=0)
    count_spinners: int = Field(default=0)
    deleted_at: datetime | None = Field(default=None, sa_column=Column(DateTime))
    hit_length: int = Field(default=0)
    last_updated: datetime = Field(sa_column=Column(DateTime, index=True))


class Beatmap(BeatmapBase, table=True):
    __tablename__ = "beatmaps"  # pyright: ignore[reportAssignmentType]
    id: int = Field(primary_key=True, index=True)
    beatmapset_id: int = Field(foreign_key="beatmapsets.id", index=True)
    beatmap_status: BeatmapRankStatus = Field(index=True)
    # optional
    beatmapset: Beatmapset = Relationship(
        back_populates="beatmaps", sa_relationship_kwargs={"lazy": "joined"}
    )

    @classmethod
    async def from_resp(cls, session: AsyncSession, resp: "BeatmapResp") -> "Beatmap":
        d = resp.model_dump()
        del d["beatmapset"]
        beatmap = Beatmap.model_validate(
            {
                **d,
                "beatmapset_id": resp.beatmapset_id,
                "id": resp.id,
                "beatmap_status": BeatmapRankStatus(resp.ranked),
            }
        )
        session.add(beatmap)
        await session.commit()
        beatmap = (
            await session.exec(select(Beatmap).where(Beatmap.id == resp.id))
        ).first()
        assert beatmap is not None, "Beatmap should not be None after commit"
        return beatmap

    @classmethod
    async def from_resp_batch(
        cls, session: AsyncSession, inp: list["BeatmapResp"], from_: int = 0
    ) -> list["Beatmap"]:
        beatmaps = []
        for resp in inp:
            if resp.id == from_:
                continue
            d = resp.model_dump()
            del d["beatmapset"]
            beatmap = Beatmap.model_validate(
                {
                    **d,
                    "beatmapset_id": resp.beatmapset_id,
                    "id": resp.id,
                    "beatmap_status": BeatmapRankStatus(resp.ranked),
                }
            )
            session.add(beatmap)
            beatmaps.append(beatmap)
        await session.commit()
        return beatmaps

    @classmethod
    async def get_or_fetch(
        cls,
        session: AsyncSession,
        fetcher: "Fetcher",
        bid: int | None = None,
        md5: str | None = None,
    ) -> "Beatmap":
        beatmap = (
            await session.exec(
                select(Beatmap).where(
                    Beatmap.id == bid if bid is not None else Beatmap.checksum == md5
                )
            )
        ).first()
        if not beatmap:
            resp = await fetcher.get_beatmap(bid, md5)
            r = await session.exec(
                select(Beatmapset.id).where(Beatmapset.id == resp.beatmapset_id)
            )
            if not r.first():
                set_resp = await fetcher.get_beatmapset(resp.beatmapset_id)
                await Beatmapset.from_resp(session, set_resp, from_=resp.id)
            return await Beatmap.from_resp(session, resp)
        return beatmap


class BeatmapResp(BeatmapBase):
    id: int
    beatmapset_id: int
    beatmapset: BeatmapsetResp | None = None
    convert: bool = False
    is_scoreable: bool
    status: str
    mode_int: int
    ranked: int
    url: str = ""
    playcount: int = 0
    passcount: int = 0

    @classmethod
    async def from_db(
        cls,
        beatmap: Beatmap,
        query_mode: GameMode | None = None,
        from_set: bool = False,
        session: AsyncSession | None = None,
        user: "User | None" = None,
    ) -> "BeatmapResp":
        from .score import Score

        beatmap_ = beatmap.model_dump()
        beatmap_status = beatmap.beatmap_status
        if query_mode is not None and beatmap.mode != query_mode:
            beatmap_["convert"] = True
        beatmap_["is_scoreable"] = beatmap_status.has_leaderboard()
        if (
            settings.enable_all_beatmap_leaderboard
            and not beatmap_status.has_leaderboard()
        ):
            beatmap_["ranked"] = BeatmapRankStatus.APPROVED.value
            beatmap_["status"] = BeatmapRankStatus.APPROVED.name.lower()
        else:
            beatmap_["status"] = beatmap_status.name.lower()
            beatmap_["ranked"] = beatmap_status.value
        beatmap_["mode_int"] = int(beatmap.mode)
        if not from_set:
            beatmap_["beatmapset"] = await BeatmapsetResp.from_db(
                beatmap.beatmapset, session=session, user=user
            )
        if session:
            beatmap_["playcount"] = (
                await session.exec(
                    select(func.count())
                    .select_from(BeatmapPlaycounts)
                    .where(BeatmapPlaycounts.beatmap_id == beatmap.id)
                )
            ).one()
            beatmap_["passcount"] = (
                await session.exec(
                    select(func.count())
                    .select_from(Score)
                    .where(
                        Score.beatmap_id == beatmap.id,
                        col(Score.passed).is_(True),
                    )
                )
            ).one()
        return cls.model_validate(beatmap_)


class BannedBeatmaps(SQLModel, table=True):
    __tablename__ = "banned_beatmaps"  # pyright: ignore[reportAssignmentType]
    id: int = Field(primary_key=True, index=True)
    beatmap_id: int = Field(index=True)


async def calculate_beatmap_attributes(
    beatmap_id: int,
    ruleset: GameMode,
    mods_: list[APIMod],
    redis: Redis,
    fetcher: "Fetcher",
):
    key = (
        f"beatmap:{beatmap_id}:{ruleset}:"
        f"{hashlib.md5(str(mods_).encode()).hexdigest()}:attributes"
    )
    if await redis.exists(key):
        return BeatmapAttributes.model_validate_json(await redis.get(key))  # pyright: ignore[reportArgumentType]
    resp = await fetcher.get_or_fetch_beatmap_raw(redis, beatmap_id)
    # 延迟导入以解决循环导入问题
    from app.calculator import calculate_beatmap_attribute

    attr = await asyncio.get_event_loop().run_in_executor(
        None, calculate_beatmap_attribute, resp, ruleset, mods_
    )
    await redis.set(key, attr.model_dump_json())
    return attr
