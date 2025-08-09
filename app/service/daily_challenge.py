from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json

from app.database.playlists import Playlist
from app.database.room import Room
from app.dependencies.database import engine, get_redis
from app.dependencies.scheduler import get_scheduler
from app.log import logger
from app.models.metadata_hub import DailyChallengeInfo
from app.models.mods import APIMod
from app.models.room import RoomCategory

from .room import create_playlist_room

from sqlmodel.ext.asyncio.session import AsyncSession


async def create_daily_challenge_room(
    beatmap: int, ruleset_id: int, required_mods: list[APIMod] = []
) -> Room:
    async with AsyncSession(engine) as session:
        today = datetime.now(UTC).date()
        return await create_playlist_room(
            session=session,
            name=str(today),
            host_id=3,
            playlist=[
                Playlist(
                    id=0,
                    room_id=0,
                    owner_id=3,
                    ruleset_id=ruleset_id,
                    beatmap_id=beatmap,
                    required_mods=required_mods,
                )
            ],
            category=RoomCategory.DAILY_CHALLENGE,
            duration=24 * 60 - 2,  # remain 2 minute to apply new daily challenge
        )


@get_scheduler().scheduled_job("cron", hour=0, minute=0, second=0, id="daily_challenge")
async def daily_challenge_job():
    from app.signalr.hub import MetadataHubs

    today = datetime.now(UTC).date()
    redis = get_redis()
    key = f"daily_challenge:{today}"
    if not await redis.exists(key):
        return
    try:
        beatmap = await redis.hget(key, "beatmap")  # pyright: ignore[reportGeneralTypeIssues]
        ruleset_id = await redis.hget(key, "ruleset_id")  # pyright: ignore[reportGeneralTypeIssues]
        required_mods = await redis.hget(key, "required_mods")  # pyright: ignore[reportGeneralTypeIssues]

        if beatmap is None or ruleset_id is None:
            logger.warning(
                f"[DailyChallenge] Missing required data for daily challenge {today}."
                " Will try again in 5 minutes."
            )
            get_scheduler().add_job(
                daily_challenge_job,
                "date",
                run_date=datetime.now(UTC) + timedelta(minutes=5),
            )
            return

        beatmap_int = int(beatmap)
        ruleset_id_int = int(ruleset_id)

        mods_list = []
        if required_mods:
            mods_list = json.loads(required_mods)

        room = await create_daily_challenge_room(
            beatmap=beatmap_int,
            ruleset_id=ruleset_id_int,
            required_mods=mods_list,
        )
        await MetadataHubs.broadcast_call(
            "DailyChallengeUpdated", DailyChallengeInfo(room_id=room.id)
        )
        logger.success(
            "[DailyChallenge] Added today's daily challenge: "
            f"{beatmap=}, {ruleset_id=}, {required_mods=}"
        )
        return
    except (ValueError, json.JSONDecodeError) as e:
        logger.warning(
            f"[DailyChallenge] Error processing daily challenge data: {e}"
            " Will try again in 5 minutes."
        )
    except Exception as e:
        logger.exception(
            f"[DailyChallenge] Unexpected error in daily challenge job: {e}"
            " Will try again in 5 minutes."
        )
    get_scheduler().add_job(
        daily_challenge_job,
        "date",
        run_date=datetime.now(UTC) + timedelta(minutes=5),
    )
