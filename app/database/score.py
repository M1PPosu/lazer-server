from datetime import datetime
import math

from app.database.user import User
from app.models.beatmap import BeatmapRankStatus
from app.models.mods import APIMod
from app.models.score import (
    MODE_TO_INT,
    GameMode,
    HitResult,
    LeaderboardType,
    Rank,
    ScoreStatistics,
)

from .beatmap import Beatmap, BeatmapResp
from .beatmapset import Beatmapset, BeatmapsetResp

from sqlalchemy import Column, ColumnExpressionArgument, DateTime
from sqlalchemy.orm import aliased, joinedload
from sqlmodel import (
    JSON,
    BigInteger,
    Field,
    ForeignKey,
    Relationship,
    SQLModel,
    col,
    false,
    func,
    select,
)
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel.sql._expression_select_cls import SelectOfScalar


class ScoreBase(SQLModel):
    # 基本字段
    accuracy: float
    map_md5: str = Field(max_length=32, index=True)
    best_id: int | None = Field(default=None)
    build_id: int | None = Field(default=None)
    classic_total_score: int | None = Field(
        default=0, sa_column=Column(BigInteger)
    )  # solo_score
    ended_at: datetime = Field(sa_column=Column(DateTime))
    has_replay: bool
    max_combo: int
    mods: list[APIMod] = Field(sa_column=Column(JSON))
    passed: bool
    playlist_item_id: int | None = Field(default=None)  # multiplayer
    pp: float
    preserve: bool = Field(default=True)
    rank: Rank
    room_id: int | None = Field(default=None)  # multiplayer
    started_at: datetime = Field(sa_column=Column(DateTime))
    total_score: int = Field(default=0, sa_column=Column(BigInteger))
    total_score_without_mods: int = Field(
        default=0, sa_column=Column(BigInteger), exclude=True
    )
    type: str

    # optional
    # TODO: current_user_attributes
    position: int | None = Field(default=None)  # multiplayer


class Score(ScoreBase, table=True):
    __tablename__ = "scores"  # pyright: ignore[reportAssignmentType]
    id: int | None = Field(
        default=None, sa_column=Column(BigInteger, autoincrement=True, primary_key=True)
    )
    beatmap_id: int = Field(index=True, foreign_key="beatmaps.id")
    user_id: int = Field(
        default=None,
        sa_column=Column(
            BigInteger,
            ForeignKey("users.id"),
            index=True,
        ),
    )
    # ScoreStatistics
    n300: int = Field(exclude=True)
    n100: int = Field(exclude=True)
    n50: int = Field(exclude=True)
    nmiss: int = Field(exclude=True)
    ngeki: int = Field(exclude=True)
    nkatu: int = Field(exclude=True)
    nlarge_tick_miss: int | None = Field(default=None, exclude=True)
    nslider_tail_hit: int | None = Field(default=None, exclude=True)
    gamemode: GameMode = Field(index=True)

    # optional
    beatmap: "Beatmap" = Relationship()
    user: "User" = Relationship()

    @property
    def is_perfect_combo(self) -> bool:
        return self.max_combo == self.beatmap.max_combo

    @staticmethod
    def select_clause() -> SelectOfScalar["Score"]:
        return select(Score).options(
            joinedload(Score.beatmap)  # pyright: ignore[reportArgumentType]
            .joinedload(Beatmap.beatmapset)  # pyright: ignore[reportArgumentType]
            .selectinload(
                Beatmapset.beatmaps  # pyright: ignore[reportArgumentType]
            ),
            joinedload(Score.user).joinedload(User.lazer_profile),  # pyright: ignore[reportArgumentType]
        )

    @staticmethod
    def select_clause_unique(
        *where_clauses: ColumnExpressionArgument[bool] | bool,
    ) -> SelectOfScalar["Score"]:
        rownum = (
            func.row_number()
            .over(
                partition_by=col(Score.user_id), order_by=col(Score.total_score).desc()
            )
            .label("rn")
        )
        subq = select(Score, rownum).where(*where_clauses).subquery()
        best = aliased(Score, subq, adapt_on_names=True)
        return (
            select(best)
            .where(subq.c.rn == 1)
            .options(
                joinedload(best.beatmap)  # pyright: ignore[reportArgumentType]
                .joinedload(Beatmap.beatmapset)  # pyright: ignore[reportArgumentType]
                .selectinload(
                    Beatmapset.beatmaps  # pyright: ignore[reportArgumentType]
                ),
                joinedload(best.user).joinedload(User.lazer_profile),  # pyright: ignore[reportArgumentType]
            )
        )


class ScoreResp(ScoreBase):
    id: int
    user_id: int
    is_perfect_combo: bool = False
    legacy_perfect: bool = False
    legacy_total_score: int = 0  # FIXME
    processed: bool = False  # solo_score
    weight: float = 0.0
    ruleset_id: int | None = None
    beatmap: BeatmapResp | None = None
    beatmapset: BeatmapsetResp | None = None
    # FIXME: user: APIUser | None = None
    statistics: ScoreStatistics | None = None
    rank_global: int | None = None
    rank_country: int | None = None

    @classmethod
    async def from_db(cls, session: AsyncSession, score: Score) -> "ScoreResp":
        s = cls.model_validate(score.model_dump())
        assert score.id
        s.beatmap = BeatmapResp.from_db(score.beatmap)
        s.beatmapset = BeatmapsetResp.from_db(score.beatmap.beatmapset)
        s.is_perfect_combo = s.max_combo == s.beatmap.max_combo
        s.legacy_perfect = s.max_combo == s.beatmap.max_combo
        s.ruleset_id = MODE_TO_INT[score.gamemode]
        if score.best_id:
            # https://osu.ppy.sh/wiki/Performance_points/Weighting_system
            s.weight = math.pow(0.95, score.best_id)
        s.statistics = {
            HitResult.MISS: score.nmiss,
            HitResult.MEH: score.n50,
            HitResult.OK: score.n100,
            HitResult.GREAT: score.n300,
            HitResult.PERFECT: score.ngeki,
            HitResult.GOOD: score.nkatu,
        }
        if score.nlarge_tick_miss is not None:
            s.statistics[HitResult.LARGE_TICK_MISS] = score.nlarge_tick_miss
        if score.nslider_tail_hit is not None:
            s.statistics[HitResult.SLIDER_TAIL_HIT] = score.nslider_tail_hit
        # s.user = await convert_db_user_to_api_user(score.user)
        s.rank_global = (
            await get_score_position_by_id(
                session,
                score.map_md5,
                score.id,
                mode=score.gamemode,
                user=score.user,
            )
            or None
        )
        s.rank_country = (
            await get_score_position_by_id(
                session,
                score.map_md5,
                score.id,
                score.gamemode,
                score.user,
            )
            or None
        )
        return s


async def get_leaderboard(
    session: AsyncSession,
    beatmap_md5: str,
    mode: GameMode,
    type: LeaderboardType = LeaderboardType.GLOBAL,
    mods: list[APIMod] | None = None,
    user: User | None = None,
    limit: int = 50,
) -> list[Score]:
    scores = []
    if type == LeaderboardType.GLOBAL:
        query = (
            select(Score)
            .where(
                col(Beatmap.beatmap_status).in_(
                    [
                        BeatmapRankStatus.RANKED,
                        BeatmapRankStatus.LOVED,
                        BeatmapRankStatus.QUALIFIED,
                        BeatmapRankStatus.APPROVED,
                    ]
                ),
                Score.map_md5 == beatmap_md5,
                Score.gamemode == mode,
                col(Score.passed).is_(True),
                Score.mods == mods if user and user.is_supporter else false(),
            )
            .limit(limit)
            .order_by(
                col(Score.total_score).desc(),
            )
        )
        result = await session.exec(query)
        scores = list[Score](result.all())
    elif type == LeaderboardType.FRIENDS and user and user.is_supporter:
        # TODO
        ...
    elif type == LeaderboardType.TEAM and user and user.team_membership:
        team_id = user.team_membership.team_id
        query = (
            select(Score)
            .join(Beatmap)
            .options(joinedload(Score.user))  # pyright: ignore[reportArgumentType]
            .where(
                Score.map_md5 == beatmap_md5,
                Score.gamemode == mode,
                col(Score.passed).is_(True),
                col(Score.user.team_membership).is_not(None),
                Score.user.team_membership.team_id == team_id,  # pyright: ignore[reportOptionalMemberAccess]
                Score.mods == mods if user and user.is_supporter else false(),
            )
            .limit(limit)
            .order_by(
                col(Score.total_score).desc(),
            )
        )
        result = await session.exec(query)
        scores = list[Score](result.all())
    if user:
        user_score = (
            await session.exec(
                select(Score).where(
                    Score.map_md5 == beatmap_md5,
                    Score.gamemode == mode,
                    Score.user_id == user.id,
                    col(Score.passed).is_(True),
                )
            )
        ).first()
        if user_score and user_score not in scores:
            scores.append(user_score)
    return scores


async def get_score_position_by_user(
    session: AsyncSession,
    beatmap_md5: str,
    user: User,
    mode: GameMode,
    type: LeaderboardType = LeaderboardType.GLOBAL,
    mods: list[APIMod] | None = None,
) -> int:
    where_clause = [
        Score.map_md5 == beatmap_md5,
        Score.gamemode == mode,
        col(Score.passed).is_(True),
        col(Beatmap.beatmap_status).in_(
            [
                BeatmapRankStatus.RANKED,
                BeatmapRankStatus.LOVED,
                BeatmapRankStatus.QUALIFIED,
                BeatmapRankStatus.APPROVED,
            ]
        ),
    ]
    if mods and user.is_supporter:
        where_clause.append(Score.mods == mods)
    else:
        where_clause.append(false())
    if type == LeaderboardType.FRIENDS and user.is_supporter:
        # TODO
        ...
    elif type == LeaderboardType.TEAM and user.team_membership:
        team_id = user.team_membership.team_id
        where_clause.append(
            col(Score.user.team_membership).is_not(None),
        )
        where_clause.append(
            Score.user.team_membership.team_id == team_id,  # pyright: ignore[reportOptionalMemberAccess]
        )
    rownum = (
        func.row_number()
        .over(
            partition_by=Score.map_md5,
            order_by=col(Score.total_score).desc(),
        )
        .label("row_number")
    )
    subq = select(Score, rownum).join(Beatmap).where(*where_clause).subquery()
    stmt = select(subq.c.row_number).where(subq.c.user == user)
    result = await session.exec(stmt)
    s = result.one_or_none()
    return s if s else 0


async def get_score_position_by_id(
    session: AsyncSession,
    beatmap_md5: str,
    score_id: int,
    mode: GameMode,
    user: User | None = None,
    type: LeaderboardType = LeaderboardType.GLOBAL,
    mods: list[APIMod] | None = None,
) -> int:
    where_clause = [
        Score.map_md5 == beatmap_md5,
        Score.id == score_id,
        Score.gamemode == mode,
        col(Score.passed).is_(True),
        col(Beatmap.beatmap_status).in_(
            [
                BeatmapRankStatus.RANKED,
                BeatmapRankStatus.LOVED,
                BeatmapRankStatus.QUALIFIED,
                BeatmapRankStatus.APPROVED,
            ]
        ),
    ]
    if mods and user and user.is_supporter:
        where_clause.append(Score.mods == mods)
    elif mods:
        where_clause.append(false())
    rownum = (
        func.row_number()
        .over(
            partition_by=[col(Score.user_id), col(Score.map_md5)],
            order_by=col(Score.total_score).desc(),
        )
        .label("rownum")
    )
    subq = (
        select(Score.user_id, Score.id, Score.total_score, rownum)
        .join(Beatmap)
        .where(*where_clause)
        .subquery()
    )
    best_scores = aliased(subq)
    overall_rank = (
        func.rank().over(order_by=best_scores.c.total_score.desc()).label("global_rank")
    )
    final_q = (
        select(best_scores.c.id, overall_rank)
        .select_from(best_scores)
        .where(best_scores.c.rownum == 1)
        .subquery()
    )

    stmt = select(final_q.c.global_rank).where(final_q.c.id == score_id)
    result = await session.exec(stmt)
    s = result.one_or_none()
    return s if s else 0
