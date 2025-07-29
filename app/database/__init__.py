from .auth import OAuthToken
from .beatmap import (
    Beatmap as Beatmap,
    BeatmapResp as BeatmapResp,
)
from .beatmapset import (
    Beatmapset as Beatmapset,
    BeatmapsetResp as BeatmapsetResp,
)
from .best_score import BestScore
from .legacy import LegacyOAuthToken, LegacyUserStatistics
from .relationship import Relationship, RelationshipResp, RelationshipType
from .score import (
    Score,
    ScoreBase,
    ScoreResp,
    ScoreStatistics,
)
from .score_token import ScoreToken, ScoreTokenResp
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
    "BestScore",
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
    "Relationship",
    "RelationshipResp",
    "RelationshipType",
    "Score",
    "ScoreBase",
    "ScoreResp",
    "ScoreStatistics",
    "ScoreToken",
    "ScoreTokenResp",
    "Team",
    "TeamMember",
    "User",
    "UserAchievement",
    "UserAvatar",
]
