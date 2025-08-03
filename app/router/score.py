from __future__ import annotations

from app.database import (
    Beatmap,
    Playlist,
    Score,
    ScoreResp,
    ScoreToken,
    ScoreTokenResp,
    User,
)
from app.database.score import get_leaderboard, process_score, process_user
from app.dependencies.database import get_db, get_redis
from app.dependencies.fetcher import get_fetcher
from app.dependencies.user import get_current_user
from app.fetcher import Fetcher
from app.models.beatmap import BeatmapRankStatus
from app.models.score import (
    INT_TO_MODE,
    GameMode,
    LeaderboardType,
    Rank,
    SoloScoreSubmissionInfo,
)
from app.signalr.hub import MultiplayerHubs

from .api_router import router

from fastapi import Depends, Form, HTTPException, Query
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy.orm import joinedload
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession


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
        beatmap_status = (
            await db.exec(select(Beatmap.beatmap_status).where(Beatmap.id == beatmap))
        ).first()
        if beatmap_status is None:
            raise HTTPException(status_code=404, detail="Beatmap not found")
        ranked = beatmap_status in {
            BeatmapRankStatus.RANKED,
            BeatmapRankStatus.APPROVED,
        }
        score = await process_score(
            current_user,
            beatmap,
            ranked,
            score_token,
            info,
            fetcher,
            db,
            redis,
        )
        await db.refresh(current_user)
        score_id = score.id
        score_token.score_id = score_id
        await process_user(db, current_user, score, ranked)
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
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    room = MultiplayerHubs.rooms[room_id]
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
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
    # TODO: max attempts
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
    current_user: User = Depends(get_current_user),
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
    return score_resp
