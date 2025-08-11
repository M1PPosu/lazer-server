from __future__ import annotations

import asyncio
import json
import lzma
import struct
import time
from typing import override

from app.config import settings
from app.database import Beatmap, User
from app.database.score import Score
from app.database.score_token import ScoreToken
from app.dependencies.database import engine
from app.dependencies.fetcher import get_fetcher
from app.models.mods import mods_to_int
from app.models.score import LegacyReplaySoloScoreInfo, ScoreStatistics
from app.models.spectator_hub import (
    APIUser,
    FrameDataBundle,
    LegacyReplayFrame,
    ScoreInfo,
    SpectatedUserState,
    SpectatorState,
    StoreClientState,
    StoreScore,
)
from app.path import REPLAY_DIR
from app.utils import unix_timestamp_to_windows

from .hub import Client, Hub

from sqlalchemy.orm import joinedload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

READ_SCORE_TIMEOUT = 30
REPLAY_LATEST_VER = 30000016


def encode_uleb128(num: int) -> bytes | bytearray:
    if num == 0:
        return b"\x00"

    ret = bytearray()

    while num != 0:
        ret.append(num & 0x7F)
        num >>= 7
        if num != 0:
            ret[-1] |= 0x80

    return ret


def encode_string(s: str) -> bytes:
    """Write `s` into bytes (ULEB128 & string)."""
    if s:
        encoded = s.encode()
        ret = b"\x0b" + encode_uleb128(len(encoded)) + encoded
    else:
        ret = b"\x00"

    return ret


def save_replay(
    ruleset_id: int,
    md5: str,
    username: str,
    score: Score,
    statistics: ScoreStatistics,
    maximum_statistics: ScoreStatistics,
    frames: list[LegacyReplayFrame],
) -> None:
    data = bytearray()
    data.extend(struct.pack("<bi", ruleset_id, REPLAY_LATEST_VER))
    data.extend(encode_string(md5))
    data.extend(encode_string(username))
    data.extend(encode_string(f"lazer-{username}-{score.started_at.isoformat()}"))
    data.extend(
        struct.pack(
            "<hhhhhhihbi",
            score.n300,
            score.n100,
            score.n50,
            score.ngeki,
            score.nkatu,
            score.nmiss,
            score.total_score,
            score.max_combo,
            score.is_perfect_combo,
            mods_to_int(score.mods),
        )
    )
    data.extend(encode_string(""))  # hp graph
    data.extend(
        struct.pack(
            "<q",
            unix_timestamp_to_windows(round(score.started_at.timestamp())),
        )
    )

    # write frames
    # FIXME: cannot play in stable
    frame_strs = []
    last_time = 0
    for frame in frames:
        frame_strs.append(
            f"{frame.time - last_time}|{frame.mouse_x or 0.0}"
            f"|{frame.mouse_y or 0.0}|{frame.button_state}"
        )
        last_time = frame.time
    frame_strs.append("-12345|0|0|0")

    compressed = lzma.compress(
        ",".join(frame_strs).encode("ascii"), format=lzma.FORMAT_ALONE
    )
    data.extend(struct.pack("<i", len(compressed)))
    data.extend(compressed)
    data.extend(struct.pack("<q", score.id))
    assert score.id
    score_info = LegacyReplaySoloScoreInfo(
        online_id=score.id,
        mods=score.mods,
        statistics=statistics,
        maximum_statistics=maximum_statistics,
        client_version="",
        rank=score.rank,
        user_id=score.user_id,
        total_score_without_mods=score.total_score_without_mods,
    )
    compressed = lzma.compress(
        json.dumps(score_info).encode(), format=lzma.FORMAT_ALONE
    )
    data.extend(struct.pack("<i", len(compressed)))
    data.extend(compressed)

    replay_path = (
        REPLAY_DIR / f"{score.id}_{score.beatmap_id}_{score.user_id}_lazer_replay.osr"
    )
    replay_path.write_bytes(data)


class SpectatorHub(Hub[StoreClientState]):
    @staticmethod
    def group_id(user_id: int) -> str:
        return f"watch:{user_id}"

    @override
    def create_state(self, client: Client) -> StoreClientState:
        return StoreClientState(
            connection_id=client.connection_id,
            connection_token=client.connection_token,
        )

    @override
    async def _clean_state(self, state: StoreClientState) -> None:
        if state.state:
            await self._end_session(int(state.connection_id), state.state)
        for target in self.waited_clients:
            target_client = self.get_client_by_id(target)
            if target_client:
                await self.call_noblock(
                    target_client, "UserEndedWatching", int(state.connection_id)
                )

    async def on_client_connect(self, client: Client) -> None:
        tasks = [
            self.call_noblock(client, "UserBeganPlaying", user_id, store.state)
            for user_id, store in self.state.items()
            if store.state is not None
        ]
        await asyncio.gather(*tasks)

    async def BeginPlaySession(
        self, client: Client, score_token: int, state: SpectatorState
    ) -> None:
        user_id = int(client.connection_id)
        store = self.get_or_create_state(client)
        if store.state is not None:
            return
        if state.beatmap_id is None or state.ruleset_id is None:
            return

        fetcher = await get_fetcher()
        async with AsyncSession(engine) as session:
            async with session.begin():
                beatmap = await Beatmap.get_or_fetch(
                    session, fetcher, bid=state.beatmap_id
                )
                user = (
                    await session.exec(select(User).where(User.id == user_id))
                ).first()
                if not user:
                    return
                name = user.username
                store.state = state
                store.beatmap_status = beatmap.beatmap_status
                store.checksum = beatmap.checksum
                store.ruleset_id = state.ruleset_id
                store.score_token = score_token
                store.score = StoreScore(
                    score_info=ScoreInfo(
                        mods=state.mods,
                        user=APIUser(id=user_id, name=name),
                        ruleset=state.ruleset_id,
                        maximum_statistics=state.maximum_statistics,
                    )
                )
        await self.broadcast_group_call(
            self.group_id(user_id),
            "UserBeganPlaying",
            user_id,
            state,
        )

    async def SendFrameData(self, client: Client, frame_data: FrameDataBundle) -> None:
        user_id = int(client.connection_id)
        state = self.get_or_create_state(client)
        if not state.score:
            return
        state.score.score_info.accuracy = frame_data.header.accuracy
        state.score.score_info.combo = frame_data.header.combo
        state.score.score_info.max_combo = frame_data.header.max_combo
        state.score.score_info.statistics = frame_data.header.statistics
        state.score.score_info.total_score = frame_data.header.total_score
        state.score.score_info.mods = frame_data.header.mods
        state.score.replay_frames.extend(frame_data.frames)
        await self.broadcast_group_call(
            self.group_id(user_id),
            "UserSentFrames",
            user_id,
            frame_data,
        )

    async def EndPlaySession(self, client: Client, state: SpectatorState) -> None:
        user_id = int(client.connection_id)
        store = self.get_or_create_state(client)
        score = store.score
        if (
            score is None
            or store.score_token is None
            or store.beatmap_status is None
            or store.state is None
        ):
            return
        if (
            settings.enable_all_beatmap_leaderboard
            and store.beatmap_status.has_leaderboard()
        ) and any(k.is_hit() and v > 0 for k, v in score.score_info.statistics.items()):
            await self._process_score(store, client)
        store.state = None
        store.beatmap_status = None
        store.checksum = None
        store.ruleset_id = None
        store.score_token = None
        store.score = None
        await self._end_session(user_id, state)

    async def _process_score(self, store: StoreClientState, client: Client) -> None:
        user_id = int(client.connection_id)
        assert store.state is not None
        assert store.score_token is not None
        assert store.checksum is not None
        assert store.ruleset_id is not None
        assert store.score is not None
        async with AsyncSession(engine) as session:
            async with session:
                start_time = time.time()
                score_record = None
                while time.time() - start_time < READ_SCORE_TIMEOUT:
                    sub_query = select(ScoreToken.score_id).where(
                        ScoreToken.id == store.score_token,
                    )
                    result = await session.exec(
                        select(Score)
                        .options(joinedload(Score.beatmap))  # pyright: ignore[reportArgumentType]
                        .where(
                            Score.id == sub_query,
                            Score.user_id == user_id,
                        )
                    )
                    score_record = result.first()
                    if score_record:
                        break
                if not score_record:
                    return
                if not score_record.passed:
                    return
                await self.call_noblock(
                    client,
                    "UserScoreProcessed",
                    user_id,
                    score_record.id,
                )
                # save replay
                score_record.has_replay = True
                await session.commit()
                await session.refresh(score_record)
                save_replay(
                    ruleset_id=store.ruleset_id,
                    md5=store.checksum,
                    username=store.score.score_info.user.name,
                    score=score_record,
                    statistics=store.score.score_info.statistics,
                    maximum_statistics=store.score.score_info.maximum_statistics,
                    frames=store.score.replay_frames,
                )

    async def _end_session(self, user_id: int, state: SpectatorState) -> None:
        if state.state == SpectatedUserState.Playing:
            state.state = SpectatedUserState.Quit
        await self.broadcast_group_call(
            self.group_id(user_id),
            "UserFinishedPlaying",
            user_id,
            state,
        )

    async def StartWatchingUser(self, client: Client, target_id: int) -> None:
        user_id = int(client.connection_id)
        target_store = self.get_or_create_state(client)
        if target_store.state:
            await self.call_noblock(
                client,
                "UserBeganPlaying",
                target_id,
                target_store.state,
            )
        store = self.get_or_create_state(client)
        store.watched_user.add(target_id)

        self.add_to_group(client, self.group_id(target_id))

        async with AsyncSession(engine) as session:
            async with session.begin():
                username = (
                    await session.exec(select(User.username).where(User.id == user_id))
                ).first()
                if not username:
                    return
            if (target_client := self.get_client_by_id(str(target_id))) is not None:
                await self.call_noblock(
                    target_client, "UserStartedWatching", [[user_id, username]]
                )

    async def EndWatchingUser(self, client: Client, target_id: int) -> None:
        user_id = int(client.connection_id)
        self.remove_from_group(client, self.group_id(target_id))
        store = self.state.get(user_id)
        if store:
            store.watched_user.discard(target_id)
        if (target_client := self.get_client_by_id(str(target_id))) is not None:
            await self.call_noblock(target_client, "UserEndedWatching", user_id)
