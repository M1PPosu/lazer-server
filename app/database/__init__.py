from __future__ import annotations

from .auth import OAuthToken
from .beatmap import (
    Beatmap as Beatmap,
    BeatmapResp as BeatmapResp,
)
from .beatmapset import (
    Beatmapset as Beatmapset,
    BeatmapsetResp as BeatmapsetResp,
)
from .legacy import LegacyOAuthToken, LegacyUserStatistics
from .team import Team, TeamMember
from .user import (
    DailyChallengeStats,
    LazerUserAchievement,
    LazerUserBadge,
    LazerUserBanners,
    LazerUserCountry,
    LazerUserCounts,
    LazerUserKudosu,
    LazerUserMonthlyPlaycounts,
    LazerUserPreviousUsername,
    LazerUserProfile,
    LazerUserProfileSections,
    LazerUserReplaysWatched,
    LazerUserStatistics,
    RankHistory,
    User,
    UserAchievement,
    UserAvatar,
)

BeatmapsetResp.model_rebuild()
BeatmapResp.model_rebuild()
__all__ = [
    "Beatmap",
    "BeatmapResp",
    "Beatmapset",
    "BeatmapsetResp",
    "DailyChallengeStats",
    "LazerUserAchievement",
    "LazerUserBadge",
    "LazerUserBanners",
    "LazerUserCountry",
    "LazerUserCounts",
    "LazerUserKudosu",
    "LazerUserMonthlyPlaycounts",
    "LazerUserPreviousUsername",
    "LazerUserProfile",
    "LazerUserProfileSections",
    "LazerUserReplaysWatched",
    "LazerUserStatistics",
    "LegacyOAuthToken",
    "LegacyUserStatistics",
    "OAuthToken",
    "RankHistory",
    "Team",
    "TeamMember",
    "User",
    "UserAchievement",
    "UserAvatar",
]
