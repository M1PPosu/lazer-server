from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from math import ceil
import random
import shlex

from app.const import BANCHOBOT_ID
from app.database import ChatMessageResp
from app.database.chat import ChannelType, ChatChannel, ChatMessage, MessageType
from app.database.lazer_user import User
from app.database.score import Score
from app.database.statistics import UserStatistics, get_rank
from app.models.score import GameMode

from .server import server

from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

HandlerResult = str | None | Awaitable[str | None]
Handler = Callable[[User, list[str], AsyncSession], HandlerResult]


class Bot:
    def __init__(self, bot_user_id: int = BANCHOBOT_ID) -> None:
        self._handlers: dict[str, Handler] = {}
        self.bot_user_id = bot_user_id

    # decorator: @bot.command("ping")
    def command(self, name: str) -> Callable[[Handler], Handler]:
        def _decorator(func: Handler) -> Handler:
            self._handlers[name.lower()] = func
            return func

        return _decorator

    def parse(self, content: str) -> tuple[str, list[str]] | None:
        if not content or not content.startswith("!"):
            return None
        try:
            parts = shlex.split(content[1:])
        except ValueError:
            parts = content[1:].split()
        if not parts:
            return None
        cmd = parts[0].lower()
        args = parts[1:]
        return cmd, args

    async def try_handle(
        self,
        user: User,
        channel: ChatChannel,
        content: str,
        session: AsyncSession,
    ) -> None:
        parsed = self.parse(content)
        if not parsed:
            return
        cmd, args = parsed
        handler = self._handlers.get(cmd)

        reply: str | None = None
        if handler is None:
            return
        else:
            res = handler(user, args, session)
            if asyncio.iscoroutine(res):
                res = await res
            reply = res  # type: ignore[assignment]

        if reply:
            await self._send_reply(user, channel, reply, session)

    async def _send_message(
        self, channel: ChatChannel, content: str, session: AsyncSession
    ) -> None:
        bot = await session.get(User, self.bot_user_id)
        if bot is None:
            return
        channel_id = channel.channel_id
        if channel_id is None:
            return

        assert bot.id is not None
        msg = ChatMessage(
            channel_id=channel_id,
            content=content,
            sender_id=bot.id,
            type=MessageType.PLAIN,
        )
        session.add(msg)
        await session.commit()
        await session.refresh(msg)
        await session.refresh(bot)
        resp = await ChatMessageResp.from_db(msg, session, bot)
        await server.send_message_to_channel(resp)

    async def _ensure_pm_channel(
        self, user: User, session: AsyncSession
    ) -> ChatChannel | None:
        user_id = user.id
        if user_id is None:
            return None

        bot = await session.get(User, self.bot_user_id)
        if bot is None or bot.id is None:
            return None

        channel = await ChatChannel.get_pm_channel(user_id, bot.id, session)
        if channel is None:
            channel = ChatChannel(
                name=f"pm_{user_id}_{bot.id}",
                description="Private message channel",
                type=ChannelType.PM,
            )
            session.add(channel)
            await session.commit()
            await session.refresh(channel)
            await session.refresh(user)
            await session.refresh(bot)
        await server.batch_join_channel([user, bot], channel, session)
        return channel

    async def _send_reply(
        self,
        user: User,
        src_channel: ChatChannel,
        content: str,
        session: AsyncSession,
    ) -> None:
        target_channel = src_channel
        if src_channel.type == ChannelType.PUBLIC:
            pm = await self._ensure_pm_channel(user, session)
            if pm is not None:
                target_channel = pm
        await self._send_message(target_channel, content, session)


bot = Bot()


@bot.command("help")
async def _help(user: User, args: list[str], _session: AsyncSession) -> str:
    cmds = sorted(bot._handlers.keys())
    if args:
        target = args[0].lower()
        if target in bot._handlers:
            return f"Use: !{target} [args]"
        return f"No such command: {target}"
    if not cmds:
        return "No available commands"
    return "Available: " + ", ".join(f"!{c}" for c in cmds)


@bot.command("roll")
def _roll(user: User, args: list[str], _session: AsyncSession) -> str:
    if len(args) > 0 and args[0].isdigit():
        r = random.randint(1, int(args[0]))
    else:
        r = random.randint(1, 100)
    return f"{user.username} rolls {r} point(s)"


@bot.command("stats")
async def _stats(user: User, args: list[str], session: AsyncSession) -> str:
    if len(args) < 1:
        return "Usage: !stats <username>"

    target_user = (
        await session.exec(select(User).where(User.username == args[0]))
    ).first()
    if not target_user:
        return f"User '{args[0]}' not found."

    gamemode = None
    if len(args) >= 2:
        gamemode = GameMode.parse(args[1].upper())
    if gamemode is None:
        subquery = (
            select(func.max(Score.id))
            .where(Score.user_id == target_user.id)
            .scalar_subquery()
        )
        last_score = (
            await session.exec(select(Score).where(Score.id == subquery))
        ).first()
        if last_score is not None:
            gamemode = last_score.gamemode
        else:
            gamemode = target_user.playmode

    statistics = (
        await session.exec(
            select(UserStatistics).where(
                UserStatistics.user_id == target_user.id,
                UserStatistics.mode == gamemode,
            )
        )
    ).first()
    if not statistics:
        return f"User '{args[0]}' has no statistics."

    return f"""Stats for {target_user.username} ({gamemode.name.lower()}):
Score: {statistics.total_score} (#{await get_rank(session, statistics)})
Plays: {statistics.play_count} (lv{ceil(statistics.level_current)})
Accuracy: {statistics.hit_accuracy}
PP: {statistics.pp}
"""
