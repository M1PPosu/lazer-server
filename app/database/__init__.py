from .achievement import UserAchievement, UserAchievementResp
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
from .daily_challenge import DailyChallengeStats, DailyChallengeStatsResp
from .lazer_user import (
    User,
    UserResp,
)
from .relationship import Relationship, RelationshipResp, RelationshipType
from .score import (
    Score,
    ScoreBase,
    ScoreResp,
    ScoreStatistics,
)
from .score_token import ScoreToken, ScoreTokenResp
from .statistics import (
    UserStatistics,
    UserStatisticsResp,
)
from .team import Team, TeamMember
from .user_account_history import (
    UserAccountHistory,
    UserAccountHistoryResp,
    UserAccountHistoryType,
)

__all__ = [
    "Beatmap",
    "BeatmapResp",
    "Beatmapset",
    "BeatmapsetResp",
    "BestScore",
    "DailyChallengeStats",
    "DailyChallengeStatsResp",
    "OAuthToken",
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
    "UserAccountHistory",
    "UserAccountHistoryResp",
    "UserAccountHistoryType",
    "UserAchievement",
    "UserAchievement",
    "UserAchievementResp",
    "UserResp",
    "UserStatistics",
    "UserStatisticsResp",
]

for i in __all__:
    if i.endswith("Resp"):
        globals()[i].model_rebuild()  # type: ignore[call-arg]
