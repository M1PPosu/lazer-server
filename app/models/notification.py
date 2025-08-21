from __future__ import annotations

from abc import abstractmethod
from enum import Enum
from typing import TYPE_CHECKING

from app.utils import truncate

from pydantic import BaseModel, PrivateAttr
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

CONTENT_TRUNCATE = 36

if TYPE_CHECKING:
    from app.database import ChannelType, ChatMessage, User


# https://github.com/ppy/osu-web/blob/master/app/Models/Notification.php
class NotificationName(str, Enum):
    BEATMAP_OWNER_CHANGE = "beatmap_owner_change"
    BEATMAPSET_DISCUSSION_LOCK = "beatmapset_discussion_lock"
    BEATMAPSET_DISCUSSION_POST_NEW = "beatmapset_discussion_post_new"
    BEATMAPSET_DISCUSSION_QUALIFIED_PROBLEM = "beatmapset_discussion_qualified_problem"
    BEATMAPSET_DISCUSSION_REVIEW_NEW = "beatmapset_discussion_review_new"
    BEATMAPSET_DISCUSSION_UNLOCK = "beatmapset_discussion_unlock"
    BEATMAPSET_DISQUALIFY = "beatmapset_disqualify"
    BEATMAPSET_LOVE = "beatmapset_love"
    BEATMAPSET_NOMINATE = "beatmapset_nominate"
    BEATMAPSET_QUALIFY = "beatmapset_qualify"
    BEATMAPSET_RANK = "beatmapset_rank"
    BEATMAPSET_REMOVE_FROM_LOVED = "beatmapset_remove_from_loved"
    BEATMAPSET_RESET_NOMINATIONS = "beatmapset_reset_nominations"
    CHANNEL_ANNOUNCEMENT = "channel_announcement"
    CHANNEL_MESSAGE = "channel_message"
    CHANNEL_TEAM = "channel_team"
    COMMENT_NEW = "comment_new"
    FORUM_TOPIC_REPLY = "forum_topic_reply"
    TEAM_APPLICATION_ACCEPT = "team_application_accept"
    TEAM_APPLICATION_REJECT = "team_application_reject"
    TEAM_APPLICATION_STORE = "team_application_store"
    USER_ACHIEVEMENT_UNLOCK = "user_achievement_unlock"
    USER_BEATMAPSET_NEW = "user_beatmapset_new"
    USER_BEATMAPSET_REVIVE = "user_beatmapset_revive"

    # NAME_TO_CATEGORY
    @property
    def category(self) -> str:
        return {
            NotificationName.BEATMAP_OWNER_CHANGE: "beatmap_owner_change",
            NotificationName.BEATMAPSET_DISCUSSION_LOCK: "beatmapset_discussion",
            NotificationName.BEATMAPSET_DISCUSSION_POST_NEW: "beatmapset_discussion",
            NotificationName.BEATMAPSET_DISCUSSION_QUALIFIED_PROBLEM: "beatmapset_problem",  # noqa: E501
            NotificationName.BEATMAPSET_DISCUSSION_REVIEW_NEW: "beatmapset_discussion",
            NotificationName.BEATMAPSET_DISCUSSION_UNLOCK: "beatmapset_discussion",
            NotificationName.BEATMAPSET_DISQUALIFY: "beatmapset_state",
            NotificationName.BEATMAPSET_LOVE: "beatmapset_state",
            NotificationName.BEATMAPSET_NOMINATE: "beatmapset_state",
            NotificationName.BEATMAPSET_QUALIFY: "beatmapset_state",
            NotificationName.BEATMAPSET_RANK: "beatmapset_state",
            NotificationName.BEATMAPSET_REMOVE_FROM_LOVED: "beatmapset_state",
            NotificationName.BEATMAPSET_RESET_NOMINATIONS: "beatmapset_state",
            NotificationName.CHANNEL_ANNOUNCEMENT: "announcement",
            NotificationName.CHANNEL_MESSAGE: "channel",
            NotificationName.CHANNEL_TEAM: "channel_team",
            NotificationName.COMMENT_NEW: "comment",
            NotificationName.FORUM_TOPIC_REPLY: "forum_topic_reply",
            NotificationName.TEAM_APPLICATION_ACCEPT: "team_application",
            NotificationName.TEAM_APPLICATION_REJECT: "team_application",
            NotificationName.TEAM_APPLICATION_STORE: "team_application",
            NotificationName.USER_ACHIEVEMENT_UNLOCK: "user_achievement_unlock",
            NotificationName.USER_BEATMAPSET_NEW: "user_beatmapset_new",
            NotificationName.USER_BEATMAPSET_REVIVE: "user_beatmapset_new",
        }[self]


class NotificationDetail(BaseModel):
    @property
    @abstractmethod
    def name(self) -> NotificationName:
        raise NotImplementedError

    @property
    @abstractmethod
    def object_type(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def object_id(self) -> int:
        raise NotImplementedError

    @property
    @abstractmethod
    def source_user_id(self) -> int:
        raise NotImplementedError

    @abstractmethod
    async def get_receivers(self, session: AsyncSession) -> list[int]:
        raise NotImplementedError


class ChannelMessageBase(NotificationDetail):
    title: str = ""
    type: str = ""
    cover_url: str = ""

    _message: "ChatMessage" = PrivateAttr()
    _user: "User" = PrivateAttr()
    _receiver: list[int] = PrivateAttr()

    def __init__(
        self,
        message: "ChatMessage",
        user: "User",
        receiver: list[int],
        channel_type: "ChannelType",
    ) -> None:
        super().__init__(
            title=truncate(message.content, CONTENT_TRUNCATE),
            type=channel_type.value.lower(),
            cover_url=user.avatar_url,
        )
        self._message = message
        self._user = user
        self._receiver = receiver

    async def get_receivers(self, session: AsyncSession) -> list[int]:
        return self._receiver

    @property
    def source_user_id(self) -> int:
        return self._user.id

    @property
    def object_type(self) -> str:
        return "channel"

    @property
    def object_id(self) -> int:
        return self._message.channel_id


class ChannelMessage(ChannelMessageBase):
    def __init__(
        self,
        message: "ChatMessage",
        user: "User",
        receiver: list[int],
        channel_type: "ChannelType",
    ) -> None:
        super().__init__(message, user, receiver, channel_type)

    @property
    def name(self) -> NotificationName:
        return NotificationName.CHANNEL_MESSAGE


class ChannelMessageTeam(ChannelMessageBase):
    def __init__(self, message: "ChatMessage", user: "User") -> None:
        from app.database import ChannelType

        super().__init__(message, user, [], ChannelType.TEAM)

    @property
    def name(self) -> NotificationName:
        return NotificationName.CHANNEL_TEAM

    async def get_receivers(self, session: AsyncSession) -> list[int]:
        from app.database import TeamMember

        user_team_id = (
            await session.exec(
                select(TeamMember.team_id).where(TeamMember.user_id == self._user.id)
            )
        ).first()
        if not user_team_id:
            return []
        user_ids = (
            await session.exec(
                select(TeamMember.user_id).where(TeamMember.team_id == user_team_id)
            )
        ).all()
        return list(user_ids)
