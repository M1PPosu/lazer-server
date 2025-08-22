from __future__ import annotations

import asyncio
import json
import lzma
import struct
import time
from typing import override

from app.calculator import clamp
from app.config import settings
from app.database import Beatmap, User
from app.database.failtime import FailTime, FailTimeResp
from app.database.score import Score
from app.database.score_token import ScoreToken
from app.database.statistics import UserStatistics
from app.dependencies.database import get_redis, with_db
from app.dependencies.fetcher import get_fetcher
from app.dependencies.storage import get_storage_service
from app.exception import InvokeException
from app.log import logger
from app.models.mods import APIMod, mods_to_int
from app.models.score import GameMode, LegacyReplaySoloScoreInfo, ScoreStatistics
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
from app.utils import unix_timestamp_to_windows

from .hub import Client, Hub
from .spectator_buffer import spectator_state_manager

from httpx import HTTPError
from sqlalchemy.orm import joinedload
from sqlmodel import select

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


async def save_replay(
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
    frame_strs = []
    last_time = 0
    for frame in frames:
        time = round(frame.time)
        frame_strs.append(
            f"{time - last_time}|{frame.mouse_x or 0.0}"
            f"|{frame.mouse_y or 0.0}|{frame.button_state}"
        )
        last_time = time
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

    storage_service = get_storage_service()
    replay_path = (
        f"replays/{score.id}_{score.beatmap_id}_{score.user_id}_lazer_replay.osr"
    )
    await storage_service.write_file(
        replay_path,
        bytes(data),
    )


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
        """
        Enhanced cleanup based on official osu-server-spectator implementation.
        Properly notifies watched users when spectator disconnects.
        """
        user_id = int(state.connection_id)

        # Use centralized offline status management
        from app.service.online_status_manager import online_status_manager
        await online_status_manager.set_user_offline(user_id)

        if state.state:
            await self._end_session(user_id, state.state, state)

        # Critical fix: Notify all watched users that this spectator has disconnected
        # This matches the official CleanUpState implementation
        for watched_user_id in state.watched_user:
            if (
                target_client := self.get_client_by_id(str(watched_user_id))
            ) is not None:
                await self.call_noblock(target_client, "UserEndedWatching", user_id)
                logger.debug(
                    f"[SpectatorHub] Notified {watched_user_id} that {user_id} stopped watching"
                )

    async def on_client_connect(self, client: Client) -> None:
        """
        Enhanced connection handling based on official implementation.
        Send all active player states to newly connected clients.
        """
        logger.info(f"[SpectatorHub] Client {client.user_id} connected")

        # Use centralized online status management
        from app.service.online_status_manager import online_status_manager
        await online_status_manager.set_user_online(client.user_id, "spectator")

        # Send all current player states to the new client
        # This matches the official OnConnectedAsync behavior
        active_states = []
        
        # 首先从缓冲区获取状态
        buffer_stats = spectator_state_manager.get_buffer_stats()
        if buffer_stats['active_users'] > 0:
            logger.debug(f"[SpectatorHub] Found {buffer_stats['active_users']} users in buffer")
            
            # 获取缓冲区中的所有活跃用户
            active_users = spectator_state_manager.buffer.get_all_active_users()
            for user_id in active_users:
                state = spectator_state_manager.buffer.get_user_state(user_id)
                if state and state.state == SpectatedUserState.Playing:
                    active_states.append((user_id, state))
        
        # 然后从本地状态获取
        for user_id, store in self.state.items():
            if store.state is not None and user_id not in [state[0] for state in active_states]:
                active_states.append((user_id, store.state))

        if active_states:
            logger.debug(
                f"[SpectatorHub] Sending {len(active_states)} active player states to {client.user_id}"
            )
            # Send states sequentially to avoid overwhelming the client
            for user_id, state in active_states:
                try:
                    await self.call_noblock(client, "UserBeganPlaying", user_id, state)
                except Exception as e:
                    logger.debug(
                        f"[SpectatorHub] Failed to send state for user {user_id}: {e}"
                    )

        # Also sync with MultiplayerHub for cross-hub spectating
        await self._sync_with_multiplayer_hub(client)

    async def _sync_with_multiplayer_hub(self, client: Client) -> None:
        """
        Sync with MultiplayerHub to get active multiplayer game states.
        This ensures spectators can see multiplayer games from other pages.
        """
        try:
            # Import here to avoid circular imports
            from app.signalr.hub import MultiplayerHubs

            # Check all active multiplayer rooms for playing users
            for room_id, server_room in MultiplayerHubs.rooms.items():
                for room_user in server_room.room.users:
                    # Send state for users who are playing or in results
                    if (
                        room_user.state.is_playing
                        and room_user.user_id not in self.state
                    ):
                        # Create a synthetic SpectatorState for multiplayer players
                        # 关键修复：处理多人游戏中不同用户可能选择不同谱面的情况
                        try:
                            # 获取用户选择的谱面ID（如果是自由选择模式）
                            user_beatmap_id = getattr(room_user, 'beatmap_id', None) or server_room.queue.current_item.beatmap_id
                            user_ruleset_id = room_user.ruleset_id or server_room.queue.current_item.ruleset_id or 0
                            user_mods = room_user.mods or []
                            
                            synthetic_state = SpectatorState(
                                beatmap_id=user_beatmap_id,
                                ruleset_id=user_ruleset_id,
                                mods=user_mods,
                                state=SpectatedUserState.Playing,
                                maximum_statistics={},
                            )

                            # 同步到缓冲区管理器
                            multiplayer_data = {
                                'room_id': room_id,
                                'beatmap_id': user_beatmap_id,
                                'ruleset_id': user_ruleset_id,
                                'mods': user_mods,
                                'state': room_user.state,
                                'maximum_statistics': {},
                                'is_multiplayer': True
                            }
                            await spectator_state_manager.sync_with_multiplayer(room_user.user_id, multiplayer_data)

                            await self.call_noblock(
                                client,
                                "UserBeganPlaying",
                                room_user.user_id,
                                synthetic_state,
                            )
                            logger.info(
                                f"[SpectatorHub] Sent synthetic multiplayer state for user {room_user.user_id} (beatmap: {user_beatmap_id}, ruleset: {user_ruleset_id})"
                            )
                        except Exception as e:
                            logger.debug(
                                f"[SpectatorHub] Failed to create synthetic state: {e}"
                            )
                    
                    # Critical addition: Notify about finished players in multiplayer games
                    elif (
                        hasattr(room_user.state, 'name') and room_user.state.name == 'RESULTS'
                        and room_user.user_id not in self.state
                    ):
                        try:
                            # Create a synthetic finished state
                            finished_state = SpectatorState(
                                beatmap_id=server_room.queue.current_item.beatmap_id,
                                ruleset_id=room_user.ruleset_id or 0,
                                mods=room_user.mods,
                                state=SpectatedUserState.Passed,  # Assume passed for results
                                maximum_statistics={},
                            )

                            # 也同步结束状态到缓冲区
                            await spectator_state_manager.handle_user_finished_playing(room_user.user_id, finished_state)

                            await self.call_noblock(
                                client,
                                "UserFinishedPlaying",
                                room_user.user_id,
                                finished_state,
                            )
                            logger.debug(
                                f"[SpectatorHub] Sent synthetic finished state for user {room_user.user_id}"
                            )
                        except Exception as e:
                            logger.debug(
                                f"[SpectatorHub] Failed to create synthetic finished state: {e}"
                            )

        except Exception as e:
            logger.debug(f"[SpectatorHub] Failed to sync with MultiplayerHub: {e}")
            # This is not critical, so we don't raise the exception

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
        async with with_db() as session:
            async with session.begin():
                try:
                    beatmap = await Beatmap.get_or_fetch(
                        session, fetcher, bid=state.beatmap_id
                    )
                except HTTPError:
                    raise InvokeException(f"Beatmap {state.beatmap_id} not found.")
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
        logger.info(f"[SpectatorHub] {client.user_id} began playing {state.beatmap_id}")

        # Track playing user and maintain online status
        from app.router.v2.stats import add_playing_user
        from app.service.online_status_manager import online_status_manager

        asyncio.create_task(add_playing_user(user_id))
        
        # Critical fix: Maintain metadata online presence during gameplay
        # This ensures the user appears online while playing
        await online_status_manager.refresh_user_online_status(user_id, "playing")

        # # 预缓存beatmap文件以加速后续PP计算
        # await self._preload_beatmap_for_pp_calculation(state.beatmap_id)

        # 更新缓冲区状态
        session_data = {
            'beatmap_checksum': store.checksum,
            'score_token': score_token,
            'username': name,
            'started_at': time.time()
        }
        await spectator_state_manager.handle_user_began_playing(user_id, state, session_data)

        await self.broadcast_group_call(
            self.group_id(user_id),
            "UserBeganPlaying",
            user_id,
            state,
        )

    async def SendFrameData(self, client: Client, frame_data: FrameDataBundle) -> None:
        user_id = int(client.connection_id)
        store = self.get_or_create_state(client)
        if store.state is None or store.score is None:
            return

        # Critical fix: Refresh online status during active gameplay
        # This prevents users from appearing offline while playing
        from app.service.online_status_manager import online_status_manager
        await online_status_manager.refresh_user_online_status(user_id, "playing_active")

        header = frame_data.header
        score_info = store.score.score_info
        score_info.accuracy = header.accuracy
        score_info.combo = header.combo
        score_info.max_combo = header.max_combo
        score_info.statistics = header.statistics
        store.score.replay_frames.extend(frame_data.frames)

        # 更新缓冲区的帧数据
        await spectator_state_manager.handle_frame_data(user_id, frame_data)

        await self.broadcast_group_call(
            self.group_id(user_id), "UserSentFrames", user_id, frame_data
        )

    async def EndPlaySession(self, client: Client, state: SpectatorState) -> None:
        user_id = int(client.connection_id)
        store = self.get_or_create_state(client)
        score = store.score
        
        # Early return if no active session
        if (
            score is None
            or store.score_token is None
            or store.beatmap_status is None
            or store.state is None
            or store.score is None
        ):
            return

        try:
            # Process score if conditions are met
            if (
                settings.enable_all_beatmap_leaderboard
                and store.beatmap_status.has_leaderboard()
            ) and any(k.is_hit() and v > 0 for k, v in score.score_info.statistics.items()):
                await self._process_score(store, client)
                
            # End the play session and notify watchers
            await self._end_session(user_id, state, store)

            # Remove from playing user tracking
            from app.router.v2.stats import remove_playing_user
            asyncio.create_task(remove_playing_user(user_id))
            
        finally:
            # CRITICAL FIX: Always clear state in finally block to ensure cleanup
            # This matches the official C# implementation pattern
            store.state = None
            store.beatmap_status = None
            store.checksum = None
            store.ruleset_id = None
            store.score_token = None
            store.score = None
            logger.info(f"[SpectatorHub] Cleared all session state for user {user_id}")

    async def _process_score(self, store: StoreClientState, client: Client) -> None:
        user_id = int(client.connection_id)
        assert store.state is not None
        assert store.score_token is not None
        assert store.checksum is not None
        assert store.ruleset_id is not None
        assert store.score is not None
        async with with_db() as session:
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
                await save_replay(
                    ruleset_id=store.ruleset_id,
                    md5=store.checksum,
                    username=store.score.score_info.user.name,
                    score=score_record,
                    statistics=store.score.score_info.statistics,
                    maximum_statistics=store.score.score_info.maximum_statistics,
                    frames=store.score.replay_frames,
                )

    async def _end_session(
        self, user_id: int, state: SpectatorState, store: StoreClientState
    ) -> None:
        async def _add_failtime():
            async with with_db() as session:
                failtime = await session.get(FailTime, state.beatmap_id)
                total_length = (
                    await session.exec(
                        select(Beatmap.total_length).where(
                            Beatmap.id == state.beatmap_id
                        )
                    )
                ).one()
                index = clamp(round((exit_time / total_length) * 100), 0, 99)
                if failtime is not None:
                    resp = FailTimeResp.from_db(failtime)
                else:
                    resp = FailTimeResp()
                if state.state == SpectatedUserState.Failed:
                    resp.fail[index] += 1
                elif state.state == SpectatedUserState.Quit:
                    resp.exit[index] += 1

                new_failtime = FailTime.from_resp(state.beatmap_id, resp)  # pyright: ignore[reportArgumentType]
                if failtime is not None:
                    await session.merge(new_failtime)
                else:
                    session.add(new_failtime)
                await session.commit()

        async def _edit_playtime(token: int, ruleset_id: int, mods: list[APIMod]):
            redis = get_redis()
            key = f"score:existed_time:{token}"
            messages = await redis.xrange(key, min="-", max="+", count=1)
            if not messages:
                return
            before_time = int(messages[0][1]["time"])
            await redis.delete(key)
            async with with_db() as session:
                gamemode = GameMode.from_int(ruleset_id).to_special_mode(mods)
                statistics = (
                    await session.exec(
                        select(UserStatistics).where(
                            UserStatistics.user_id == user_id,
                            UserStatistics.mode == gamemode,
                        )
                    )
                ).first()
                if statistics is None:
                    return
                statistics.play_time -= before_time
                statistics.play_time += round(min(before_time, exit_time))

        if state.state == SpectatedUserState.Playing:
            state.state = SpectatedUserState.Quit
            logger.debug(
                f"[SpectatorHub] Changed state from Playing to Quit for user {user_id}"
            )

        # Calculate exit time safely
        exit_time = 0
        if store.score and store.score.replay_frames:
            exit_time = max(frame.time for frame in store.score.replay_frames) // 1000

        # Background task for playtime editing - only if we have valid data
        if store.score_token and store.ruleset_id and store.score:
            task = asyncio.create_task(
                _edit_playtime(
                    store.score_token,
                    store.ruleset_id,
                    store.score.score_info.mods,
                )
            )
            self.tasks.add(task)
            task.add_done_callback(self.tasks.discard)

        # Background task for failtime tracking - only for failed/quit states with valid data
        if (
            state.beatmap_id is not None
            and exit_time > 0
            and state.state in (SpectatedUserState.Failed, SpectatedUserState.Quit)
        ):
            task = asyncio.create_task(_add_failtime())
            self.tasks.add(task)
            task.add_done_callback(self.tasks.discard)

        # 通知缓冲区管理器用户结束游戏
        await spectator_state_manager.handle_user_finished_playing(user_id, state)

        logger.info(
            f"[SpectatorHub] {user_id} finished playing {state.beatmap_id} "
            f"with {state.state}"
        )
        await self.broadcast_group_call(
            self.group_id(user_id),
            "UserFinishedPlaying",
            user_id,
            state,
        )

    async def StartWatchingUser(self, client: Client, target_id: int) -> None:
        """
        Enhanced StartWatchingUser based on official osu-server-spectator implementation.
        Properly handles state synchronization and watcher notifications.
        """
        user_id = int(client.connection_id)

        logger.info(f"[SpectatorHub] {user_id} started watching {target_id}")

        # 使用缓冲区管理器处理观战开始，获取追赶数据
        catchup_bundle = await spectator_state_manager.handle_spectator_start_watching(user_id, target_id)

        try:
            # 首先尝试从缓冲区获取状态
            buffered_state = spectator_state_manager.buffer.get_user_state(target_id)
            
            if buffered_state and buffered_state.state == SpectatedUserState.Playing:
                logger.info(
                    f"[SpectatorHub] Sending buffered state for {target_id} to spectator {user_id} "
                    f"(beatmap: {buffered_state.beatmap_id}, ruleset: {buffered_state.ruleset_id})"
                )
                await self.call_noblock(client, "UserBeganPlaying", target_id, buffered_state)
                
                # 发送最近的帧数据以帮助同步
                recent_frames = spectator_state_manager.buffer.get_recent_frames(target_id, 10)
                for frame_data in recent_frames:
                    try:
                        await self.call_noblock(client, "UserSentFrames", target_id, frame_data)
                    except Exception as e:
                        logger.debug(f"[SpectatorHub] Failed to send frame data: {e}")
                        
                # 如果有追赶数据包，发送额外的同步信息
                if catchup_bundle:
                    multiplayer_data = catchup_bundle.get('multiplayer_data')
                    if multiplayer_data and multiplayer_data.get('is_multiplayer'):
                        logger.info(
                            f"[SpectatorHub] Sending multiplayer sync data for {target_id} "
                            f"(room: {multiplayer_data.get('room_id')})"
                        )
            else:
                # 尝试从本地状态获取
                target_store = self.state.get(target_id)
                if target_store and target_store.state:
                    # CRITICAL FIX: Only send state if user is actually playing
                    # Don't send state for finished/quit games
                    if target_store.state.state == SpectatedUserState.Playing:
                        logger.debug(f"[SpectatorHub] {target_id} is currently playing, sending local state")
                        await self.call_noblock(client, "UserBeganPlaying", target_id, target_store.state)
                    else:
                        logger.debug(f"[SpectatorHub] {target_id} state is {target_store.state.state}, not sending to watcher")
                else:
                    # 检查多人游戏同步缓存
                    multiplayer_data = spectator_state_manager.buffer.get_multiplayer_sync_data(target_id)
                    if multiplayer_data:
                        logger.debug(f"[SpectatorHub] Sending multiplayer sync data for {target_id}")
                        # 这里可以发送多人游戏的状态信息
                        
        except Exception as e:
            # User isn't tracked or error occurred - this is not critical
            logger.debug(f"[SpectatorHub] Could not get state for {target_id}: {e}")

        # Add watcher to our tracked users
        store = self.get_or_create_state(client)
        store.watched_user.add(target_id)

        # Add to SignalR group for this target user
        self.add_to_group(client, self.group_id(target_id))

        # Get watcher's username and notify the target user
        try:
            async with with_db() as session:
                username = (
                    await session.exec(select(User.username).where(User.id == user_id))
                ).first()
                if not username:
                    logger.warning(
                        f"[SpectatorHub] Could not find username for user {user_id}"
                    )
                    return

            # Notify target user that someone started watching
            if (target_client := self.get_client_by_id(str(target_id))) is not None:
                # Create watcher info array (matches official format)
                watcher_info = [[user_id, username]]
                await self.call_noblock(
                    target_client, "UserStartedWatching", watcher_info
                )
                logger.debug(
                    f"[SpectatorHub] Notified {target_id} that {username} started watching"
                )
        except Exception as e:
            logger.error(f"[SpectatorHub] Error notifying target user {target_id}: {e}")

    async def EndWatchingUser(self, client: Client, target_id: int) -> None:
        """
        Enhanced EndWatchingUser based on official osu-server-spectator implementation.
        Properly cleans up watcher state and notifies target user.
        """
        user_id = int(client.connection_id)

        logger.info(f"[SpectatorHub] {user_id} ended watching {target_id}")

        # 使用缓冲区管理器处理观战结束
        await spectator_state_manager.handle_spectator_stop_watching(user_id, target_id)

        # Remove from SignalR group
        self.remove_from_group(client, self.group_id(target_id))

        # Remove from our tracked watched users
        store = self.get_or_create_state(client)
        store.watched_user.discard(target_id)

        # Notify target user that watcher stopped watching
        if (target_client := self.get_client_by_id(str(target_id))) is not None:
            await self.call_noblock(target_client, "UserEndedWatching", user_id)
            logger.debug(
                f"[SpectatorHub] Notified {target_id} that {user_id} stopped watching"
            )
        else:
            logger.debug(
                f"[SpectatorHub] Target user {target_id} not found for end watching notification"
            )
