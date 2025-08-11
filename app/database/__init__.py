from .achievement import UserAchievement, UserAchievementResp
from .auth import OAuthToken
from .beatmap import (
    Beatmap as Beatmap,
    BeatmapResp as BeatmapResp,
)
from .beatmap_playcounts import BeatmapPlaycounts, BeatmapPlaycountsResp
from .beatmapset import (
    Beatmapset as Beatmapset,
    BeatmapsetResp as BeatmapsetResp,
)
from .best_score import BestScore
from .counts import (
    CountResp,
    MonthlyPlaycounts,
    ReplayWatchedCount,
)
from .daily_challenge import DailyChallengeStats, DailyChallengeStatsResp
from .favourite_beatmapset import FavouriteBeatmapset
from .lazer_user import (
    User,
    UserResp,
)
from .multiplayer_event import MultiplayerEvent, MultiplayerEventResp
from .playlist_attempts import (
    ItemAttemptsCount,
    ItemAttemptsResp,
    PlaylistAggregateScore,
)
from .playlist_best_score import PlaylistBestScore
from .playlists import Playlist, PlaylistResp
from .pp_best_score import PPBestScore
from .relationship import Relationship, RelationshipResp, RelationshipType
from .room import APIUploadedRoom, Room, RoomResp
from .room_participated_user import RoomParticipatedUser
from .score import (
    MultiplayerScores,
    Score,
    ScoreAround,
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
    "APIUploadedRoom",
    "Beatmap",
    "BeatmapPlaycounts",
    "BeatmapPlaycountsResp",
    "Beatmapset",
    "BeatmapsetResp",
    "BestScore",
    "CountResp",
    "DailyChallengeStats",
    "DailyChallengeStatsResp",
    "FavouriteBeatmapset",
    "ItemAttemptsCount",
    "ItemAttemptsResp",
    "MonthlyPlaycounts",
    "MultiplayerEvent",
    "MultiplayerEventResp",
    "MultiplayerScores",
    "OAuthToken",
    "PPBestScore",
    "Playlist",
    "PlaylistAggregateScore",
    "PlaylistBestScore",
    "PlaylistResp",
    "Relationship",
    "RelationshipResp",
    "RelationshipType",
    "ReplayWatchedCount",
    "Room",
    "RoomParticipatedUser",
    "RoomResp",
    "Score",
    "ScoreAround",
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
