from __future__ import annotations

from datetime import UTC, date, datetime
import time

from app.calculator import clamp
from app.config import settings
from app.database import (
    Beatmap,
    Playlist,
    Room,
    Score,
    ScoreResp,
    ScoreToken,
    ScoreTokenResp,
    User,
)
from app.database.counts import ReplayWatchedCount
from app.database.playlist_attempts import ItemAttemptsCount
from app.database.playlist_best_score import (
    PlaylistBestScore,
    get_position,
    process_playlist_best_score,
)
from app.database.relationship import Relationship, RelationshipType
from app.database.score import (
    MultiplayerScores,
    ScoreAround,
    get_leaderboard,
    process_score,
    process_user,
)
from app.dependencies.database import get_db, get_redis
from app.dependencies.fetcher import get_fetcher
from app.dependencies.user import get_current_user
from app.fetcher import Fetcher
from app.models.room import RoomCategory
from app.models.score import (
    INT_TO_MODE,
    GameMode,
    LeaderboardType,
    Rank,
    SoloScoreSubmissionInfo,
)
from app.path import REPLAY_DIR

from .router import router

from fastapi import Body, Depends, Form, HTTPException, Query, Security
from fastapi.responses import FileResponse
from httpx import HTTPError
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy.orm import joinedload
from sqlmodel import col, exists, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

READ_SCORE_TIMEOUT = 10


async def submit_score(
    info: SoloScoreSubmissionInfo,
    beatmap: int,
    token: int,
    current_user: User,
    db: AsyncSession,
    redis: Redis,
    fetcher: Fetcher,
    item_id: int | None = None,
    room_id: int | None = None,
):
    if not info.passed:
        info.rank = Rank.F
    score_token = (
        await db.exec(
            select(ScoreToken)
            .options(joinedload(ScoreToken.beatmap))  # pyright: ignore[reportArgumentType]
            .where(ScoreToken.id == token)
        )
    ).first()
    if not score_token or score_token.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Score token not found")
    if score_token.score_id:
        score = (
            await db.exec(
                select(Score).where(
                    Score.id == score_token.score_id,
                    Score.user_id == current_user.id,
                )
            )
        ).first()
        if not score:
            raise HTTPException(status_code=404, detail="Score not found")
    else:
        try:
            db_beatmap = await Beatmap.get_or_fetch(db, fetcher, bid=beatmap)
        except HTTPError:
            raise HTTPException(status_code=404, detail="Beatmap not found")
        ranked = (
            db_beatmap.beatmap_status.has_pp() | settings.enable_all_beatmap_leaderboard
        )
        beatmap_length = db_beatmap.total_length
        score = await process_score(
            current_user,
            beatmap,
            ranked,
            score_token,
            info,
            fetcher,
            db,
            redis,
            item_id,
            room_id,
        )
        await db.refresh(current_user)
        score_id = score.id
        score_token.score_id = score_id
        await process_user(db, current_user, score, beatmap_length, ranked)
        score = (await db.exec(select(Score).where(Score.id == score_id))).first()
        assert score is not None
    return await ScoreResp.from_db(db, score)


class BeatmapScores(BaseModel):
    scores: list[ScoreResp]
    userScore: ScoreResp | None = None


@router.get(
    "/beatmaps/{beatmap}/scores", tags=["beatmap"], response_model=BeatmapScores
)
async def get_beatmap_scores(
    beatmap: int,
    mode: GameMode,
    legacy_only: bool = Query(None),  # TODO:加入对这个参数的查询
    mods: list[str] = Query(default_factory=set, alias="mods[]"),
    type: LeaderboardType = Query(LeaderboardType.GLOBAL),
    current_user: User = Security(get_current_user, scopes=["public"]),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
):
    if legacy_only:
        raise HTTPException(
            status_code=404, detail="this server only contains lazer scores"
        )

    all_scores, user_score = await get_leaderboard(
        db, beatmap, mode, type=type, user=current_user, limit=limit, mods=mods
    )

    return BeatmapScores(
        scores=[await ScoreResp.from_db(db, score) for score in all_scores],
        userScore=await ScoreResp.from_db(db, user_score) if user_score else None,
    )


class BeatmapUserScore(BaseModel):
    position: int
    score: ScoreResp


@router.get(
    "/beatmaps/{beatmap}/scores/users/{user}",
    tags=["beatmap"],
    response_model=BeatmapUserScore,
)
async def get_user_beatmap_score(
    beatmap: int,
    user: int,
    legacy_only: bool = Query(None),
    mode: str = Query(None),
    mods: str = Query(None),  # TODO:添加mods筛选
    current_user: User = Security(get_current_user, scopes=["public"]),
    db: AsyncSession = Depends(get_db),
):
    if legacy_only:
        raise HTTPException(
            status_code=404, detail="This server only contains non-legacy scores"
        )
    user_score = (
        await db.exec(
            select(Score)
            .where(
                Score.gamemode == mode if mode is not None else True,
                Score.beatmap_id == beatmap,
                Score.user_id == user,
            )
            .order_by(col(Score.total_score).desc())
        )
    ).first()

    if not user_score:
        raise HTTPException(
            status_code=404, detail=f"Cannot find user {user}'s score on this beatmap"
        )
    else:
        resp = await ScoreResp.from_db(db, user_score)
        return BeatmapUserScore(
            position=resp.rank_global or 0,
            score=resp,
        )


@router.get(
    "/beatmaps/{beatmap}/scores/users/{user}/all",
    tags=["beatmap"],
    response_model=list[ScoreResp],
)
async def get_user_all_beatmap_scores(
    beatmap: int,
    user: int,
    legacy_only: bool = Query(None),
    ruleset: str = Query(None),
    current_user: User = Security(get_current_user, scopes=["public"]),
    db: AsyncSession = Depends(get_db),
):
    if legacy_only:
        raise HTTPException(
            status_code=404, detail="This server only contains non-legacy scores"
        )
    all_user_scores = (
        await db.exec(
            select(Score)
            .where(
                Score.gamemode == ruleset if ruleset is not None else True,
                Score.beatmap_id == beatmap,
                Score.user_id == user,
            )
            .order_by(col(Score.classic_total_score).desc())
        )
    ).all()

    return [await ScoreResp.from_db(db, score) for score in all_user_scores]


@router.post(
    "/beatmaps/{beatmap}/solo/scores", tags=["beatmap"], response_model=ScoreTokenResp
)
async def create_solo_score(
    beatmap: int,
    version_hash: str = Form(""),
    beatmap_hash: str = Form(),
    ruleset_id: int = Form(..., ge=0, le=3),
    current_user: User = Security(get_current_user, scopes=["*"]),
    db: AsyncSession = Depends(get_db),
):
    assert current_user.id
    async with db:
        score_token = ScoreToken(
            user_id=current_user.id,
            beatmap_id=beatmap,
            ruleset_id=INT_TO_MODE[ruleset_id],
        )
        db.add(score_token)
        await db.commit()
        await db.refresh(score_token)
        return ScoreTokenResp.from_db(score_token)


@router.put(
    "/beatmaps/{beatmap}/solo/scores/{token}",
    tags=["beatmap"],
    response_model=ScoreResp,
)
async def submit_solo_score(
    beatmap: int,
    token: int,
    info: SoloScoreSubmissionInfo,
    current_user: User = Security(get_current_user, scopes=["*"]),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    fetcher=Depends(get_fetcher),
):
    return await submit_score(info, beatmap, token, current_user, db, redis, fetcher)


@router.post(
    "/rooms/{room_id}/playlist/{playlist_id}/scores", response_model=ScoreTokenResp
)
async def create_playlist_score(
    room_id: int,
    playlist_id: int,
    beatmap_id: int = Form(),
    beatmap_hash: str = Form(),
    ruleset_id: int = Form(..., ge=0, le=3),
    version_hash: str = Form(""),
    current_user: User = Security(get_current_user, scopes=["*"]),
    session: AsyncSession = Depends(get_db),
):
    room = await session.get(Room, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    db_room_time = room.ends_at.replace(tzinfo=UTC) if room.ends_at else None
    if db_room_time and db_room_time < datetime.now(UTC).replace(tzinfo=UTC):
        raise HTTPException(status_code=400, detail="Room has ended")
    item = (
        await session.exec(
            select(Playlist).where(
                Playlist.id == playlist_id, Playlist.room_id == room_id
            )
        )
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Playlist not found")

    # validate
    if not item.freestyle:
        if item.ruleset_id != ruleset_id:
            raise HTTPException(
                status_code=400, detail="Ruleset mismatch in playlist item"
            )
        if item.beatmap_id != beatmap_id:
            raise HTTPException(
                status_code=400, detail="Beatmap ID mismatch in playlist item"
            )
    agg = await session.exec(
        select(ItemAttemptsCount).where(
            ItemAttemptsCount.room_id == room_id,
            ItemAttemptsCount.user_id == current_user.id,
        )
    )
    agg = agg.first()
    if agg and room.max_attempts and agg.attempts >= room.max_attempts:
        raise HTTPException(
            status_code=422,
            detail="You have reached the maximum attempts for this room",
        )
    if item.expired:
        raise HTTPException(status_code=400, detail="Playlist item has expired")
    if item.played_at:
        raise HTTPException(
            status_code=400, detail="Playlist item has already been played"
        )
    # 这里应该不用验证mod了吧。。。

    score_token = ScoreToken(
        user_id=current_user.id,
        beatmap_id=beatmap_id,
        ruleset_id=INT_TO_MODE[ruleset_id],
        playlist_item_id=playlist_id,
    )
    session.add(score_token)
    await session.commit()
    await session.refresh(score_token)
    return ScoreTokenResp.from_db(score_token)


@router.put("/rooms/{room_id}/playlist/{playlist_id}/scores/{token}")
async def submit_playlist_score(
    room_id: int,
    playlist_id: int,
    token: int,
    info: SoloScoreSubmissionInfo,
    current_user: User = Security(get_current_user, scopes=["*"]),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    fetcher: Fetcher = Depends(get_fetcher),
):
    item = (
        await session.exec(
            select(Playlist).where(
                Playlist.id == playlist_id, Playlist.room_id == room_id
            )
        )
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Playlist item not found")

    user_id = current_user.id
    score_resp = await submit_score(
        info,
        item.beatmap_id,
        token,
        current_user,
        session,
        redis,
        fetcher,
        item.id,
        room_id,
    )
    await process_playlist_best_score(
        room_id,
        playlist_id,
        user_id,
        score_resp.id,
        score_resp.total_score,
        session,
        redis,
    )
    await ItemAttemptsCount.get_or_create(room_id, user_id, session)
    return score_resp


class IndexedScoreResp(MultiplayerScores):
    total: int
    user_score: ScoreResp | None = None


@router.get(
    "/rooms/{room_id}/playlist/{playlist_id}/scores", response_model=IndexedScoreResp
)
async def index_playlist_scores(
    room_id: int,
    playlist_id: int,
    limit: int = 50,
    cursor: int = Query(2000000, alias="cursor[total_score]"),
    current_user: User = Security(get_current_user, scopes=["public"]),
    session: AsyncSession = Depends(get_db),
):
    room = await session.get(Room, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    limit = clamp(limit, 1, 50)

    scores = (
        await session.exec(
            select(PlaylistBestScore)
            .where(
                PlaylistBestScore.playlist_id == playlist_id,
                PlaylistBestScore.room_id == room_id,
                PlaylistBestScore.total_score < cursor,
            )
            .order_by(col(PlaylistBestScore.total_score).desc())
            .limit(limit + 1)
        )
    ).all()
    has_more = len(scores) > limit
    if has_more:
        scores = scores[:-1]

    user_score = None
    score_resp = [await ScoreResp.from_db(session, score.score) for score in scores]
    for score in score_resp:
        score.position = await get_position(room_id, playlist_id, score.id, session)
        if score.user_id == current_user.id:
            user_score = score

    if room.category == RoomCategory.DAILY_CHALLENGE:
        score_resp = [s for s in score_resp if s.passed]
        if user_score and not user_score.passed:
            user_score = None

    resp = IndexedScoreResp(
        scores=score_resp,
        user_score=user_score,
        total=len(scores),
        params={
            "limit": limit,
        },
    )
    if has_more:
        resp.cursor = {
            "total_score": scores[-1].total_score,
        }
    return resp


@router.get(
    "/rooms/{room_id}/playlist/{playlist_id}/scores/{score_id}",
    response_model=ScoreResp,
)
async def show_playlist_score(
    room_id: int,
    playlist_id: int,
    score_id: int,
    current_user: User = Security(get_current_user, scopes=["*"]),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    room = await session.get(Room, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    start_time = time.time()
    score_record = None
    completed = room.category != RoomCategory.REALTIME
    while time.time() - start_time < READ_SCORE_TIMEOUT:
        if score_record is None:
            score_record = (
                await session.exec(
                    select(PlaylistBestScore).where(
                        PlaylistBestScore.score_id == score_id,
                        PlaylistBestScore.playlist_id == playlist_id,
                        PlaylistBestScore.room_id == room_id,
                    )
                )
            ).first()
        if completed_players := await redis.get(
            f"multiplayer:{room_id}:gameplay:players"
        ):
            completed = completed_players == "0"
        if score_record and completed:
            break
    if not score_record:
        raise HTTPException(status_code=404, detail="Score not found")
    resp = await ScoreResp.from_db(session, score_record.score)
    resp.position = await get_position(room_id, playlist_id, score_id, session)
    if completed:
        scores = (
            await session.exec(
                select(PlaylistBestScore).where(
                    PlaylistBestScore.playlist_id == playlist_id,
                    PlaylistBestScore.room_id == room_id,
                )
            )
        ).all()
        higher_scores = []
        lower_scores = []
        for score in scores:
            if score.total_score > resp.total_score:
                higher_scores.append(await ScoreResp.from_db(session, score.score))
            elif score.total_score < resp.total_score:
                lower_scores.append(await ScoreResp.from_db(session, score.score))
        resp.scores_around = ScoreAround(
            higher=MultiplayerScores(scores=higher_scores),
            lower=MultiplayerScores(scores=lower_scores),
        )

    return resp


@router.get(
    "rooms/{room_id}/playlist/{playlist_id}/scores/users/{user_id}",
    response_model=ScoreResp,
)
async def get_user_playlist_score(
    room_id: int,
    playlist_id: int,
    user_id: int,
    current_user: User = Security(get_current_user, scopes=["*"]),
    session: AsyncSession = Depends(get_db),
):
    score_record = None
    start_time = time.time()
    while time.time() - start_time < READ_SCORE_TIMEOUT:
        score_record = (
            await session.exec(
                select(PlaylistBestScore).where(
                    PlaylistBestScore.user_id == user_id,
                    PlaylistBestScore.playlist_id == playlist_id,
                    PlaylistBestScore.room_id == room_id,
                )
            )
        ).first()
        if score_record:
            break
    if not score_record:
        raise HTTPException(status_code=404, detail="Score not found")

    resp = await ScoreResp.from_db(session, score_record.score)
    resp.position = await get_position(
        room_id, playlist_id, score_record.score_id, session
    )
    return resp


@router.put("/score-pins/{score}", status_code=204)
async def pin_score(
    score: int,
    current_user: User = Security(get_current_user, scopes=["*"]),
    db: AsyncSession = Depends(get_db),
):
    score_record = (
        await db.exec(
            select(Score).where(
                Score.id == score,
                Score.user_id == current_user.id,
                col(Score.passed).is_(True),
            )
        )
    ).first()
    if not score_record:
        raise HTTPException(status_code=404, detail="Score not found")

    if score_record.pinned_order > 0:
        return

    next_order = (
        (
            await db.exec(
                select(func.max(Score.pinned_order)).where(
                    Score.user_id == current_user.id,
                    Score.gamemode == score_record.gamemode,
                )
            )
        ).first()
        or 0
    ) + 1
    score_record.pinned_order = next_order
    await db.commit()


@router.delete("/score-pins/{score}", status_code=204)
async def unpin_score(
    score: int,
    current_user: User = Security(get_current_user, scopes=["*"]),
    db: AsyncSession = Depends(get_db),
):
    score_record = (
        await db.exec(
            select(Score).where(Score.id == score, Score.user_id == current_user.id)
        )
    ).first()
    if not score_record:
        raise HTTPException(status_code=404, detail="Score not found")

    if score_record.pinned_order == 0:
        return
    changed_score = (
        await db.exec(
            select(Score).where(
                Score.user_id == current_user.id,
                Score.pinned_order > score_record.pinned_order,
                Score.gamemode == score_record.gamemode,
            )
        )
    ).all()
    for s in changed_score:
        s.pinned_order -= 1
    await db.commit()


@router.post("/score-pins/{score}/reorder", status_code=204)
async def reorder_score_pin(
    score: int,
    after_score_id: int | None = Body(default=None),
    before_score_id: int | None = Body(default=None),
    current_user: User = Security(get_current_user, scopes=["*"]),
    db: AsyncSession = Depends(get_db),
):
    score_record = (
        await db.exec(
            select(Score).where(Score.id == score, Score.user_id == current_user.id)
        )
    ).first()
    if not score_record:
        raise HTTPException(status_code=404, detail="Score not found")

    if score_record.pinned_order == 0:
        raise HTTPException(status_code=400, detail="Score is not pinned")

    if (after_score_id is None) == (before_score_id is None):
        raise HTTPException(
            status_code=400,
            detail="Either after_score_id or before_score_id "
            "must be provided (but not both)",
        )

    all_pinned_scores = (
        await db.exec(
            select(Score)
            .where(
                Score.user_id == current_user.id,
                Score.pinned_order > 0,
                Score.gamemode == score_record.gamemode,
            )
            .order_by(col(Score.pinned_order))
        )
    ).all()

    target_order = None
    reference_score_id = after_score_id or before_score_id

    reference_score = next(
        (s for s in all_pinned_scores if s.id == reference_score_id), None
    )
    if not reference_score:
        detail = "After score not found" if after_score_id else "Before score not found"
        raise HTTPException(status_code=404, detail=detail)

    if after_score_id:
        target_order = reference_score.pinned_order + 1
    else:
        target_order = reference_score.pinned_order

    current_order = score_record.pinned_order

    if current_order == target_order:
        return

    updates = []

    if current_order < target_order:
        for s in all_pinned_scores:
            if current_order < s.pinned_order <= target_order and s.id != score:
                updates.append((s.id, s.pinned_order - 1))
        if after_score_id:
            final_target = (
                target_order - 1 if target_order > current_order else target_order
            )
        else:
            final_target = target_order
    else:
        for s in all_pinned_scores:
            if target_order <= s.pinned_order < current_order and s.id != score:
                updates.append((s.id, s.pinned_order + 1))
        final_target = target_order

    for score_id, new_order in updates:
        await db.exec(select(Score).where(Score.id == score_id))
        score_to_update = (
            await db.exec(select(Score).where(Score.id == score_id))
        ).first()
        if score_to_update:
            score_to_update.pinned_order = new_order

    score_record.pinned_order = final_target

    await db.commit()


@router.get("/scores/{score_id}/download")
async def download_score_replay(
    score_id: int,
    current_user: User = Security(get_current_user, scopes=["public"]),
    db: AsyncSession = Depends(get_db),
):
    score = (await db.exec(select(Score).where(Score.id == score_id))).first()
    if not score:
        raise HTTPException(status_code=404, detail="Score not found")

    filename = f"{score.id}_{score.beatmap_id}_{score.user_id}_lazer_replay.osr"
    path = REPLAY_DIR / filename

    if not path.exists():
        raise HTTPException(status_code=404, detail="Replay file not found")

    is_friend = (
        score.user_id == current_user.id
        or (
            await db.exec(
                select(exists()).where(
                    Relationship.user_id == current_user.id,
                    Relationship.target_id == score.user_id,
                    Relationship.type == RelationshipType.FOLLOW,
                )
            )
        ).first()
    )
    if not is_friend:
        replay_watched_count = (
            await db.exec(
                select(ReplayWatchedCount).where(
                    ReplayWatchedCount.user_id == score.user_id,
                    ReplayWatchedCount.year == date.today().year,
                    ReplayWatchedCount.month == date.today().month,
                )
            )
        ).first()
        if replay_watched_count is None:
            replay_watched_count = ReplayWatchedCount(
                user_id=score.user_id, year=date.today().year, month=date.today().month
            )
            db.add(replay_watched_count)
        replay_watched_count.count += 1
        await db.commit()

    return FileResponse(
        path=path, filename=filename, media_type="application/x-osu-replay"
    )
