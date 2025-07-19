from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class GameMode(str, Enum):
    OSU = "osu"
    TAIKO = "taiko"
    FRUITS = "fruits"
    MANIA = "mania"


class PlayStyle(str, Enum):
    MOUSE = "mouse"
    KEYBOARD = "keyboard"
    TABLET = "tablet"
    TOUCH = "touch"


class Country(BaseModel):
    code: str
    name: str


class Cover(BaseModel):
    custom_url: Optional[str] = None
    url: str
    id: Optional[int] = None


class Level(BaseModel):
    current: int
    progress: int


class GradeCounts(BaseModel):
    ss: int = 0
    ssh: int = 0
    s: int = 0
    sh: int = 0
    a: int = 0


class Statistics(BaseModel):
    count_100: int = 0
    count_300: int = 0
    count_50: int = 0
    count_miss: int = 0
    level: Level
    global_rank: Optional[int] = None
    global_rank_exp: Optional[int] = None
    pp: float = 0.0
    pp_exp: float = 0.0
    ranked_score: int = 0
    hit_accuracy: float = 0.0
    play_count: int = 0
    play_time: int = 0
    total_score: int = 0
    total_hits: int = 0
    maximum_combo: int = 0
    replays_watched_by_others: int = 0
    is_ranked: bool = False
    grade_counts: GradeCounts
    country_rank: Optional[int] = None
    rank: Optional[dict] = None


class Kudosu(BaseModel):
    available: int = 0
    total: int = 0


class MonthlyPlaycount(BaseModel):
    start_date: str
    count: int


class UserAchievement(BaseModel):
    achieved_at: datetime
    achievement_id: int


class RankHighest(BaseModel):
    rank: int
    updated_at: datetime


class RankHistory(BaseModel):
    mode: str
    data: List[int]


class DailyChallengeStats(BaseModel):
    daily_streak_best: int = 0
    daily_streak_current: int = 0
    last_update: Optional[datetime] = None
    last_weekly_streak: Optional[datetime] = None
    playcount: int = 0
    top_10p_placements: int = 0
    top_50p_placements: int = 0
    user_id: int
    weekly_streak_best: int = 0
    weekly_streak_current: int = 0


class Team(BaseModel):
    flag_url: str
    id: int
    name: str
    short_name: str


class Page(BaseModel):
    html: str = ""
    raw: str = ""


class User(BaseModel):
    # 基本信息
    id: int
    username: str
    avatar_url: str
    country_code: str
    default_group: str = "default"
    is_active: bool = True
    is_bot: bool = False
    is_deleted: bool = False
    is_online: bool = True
    is_supporter: bool = False
    is_restricted: bool = False
    last_visit: Optional[datetime] = None
    pm_friends_only: bool = False
    profile_colour: Optional[str] = None
    
    # 个人资料
    cover_url: Optional[str] = None
    discord: Optional[str] = None
    has_supported: bool = False
    interests: Optional[str] = None
    join_date: datetime
    location: Optional[str] = None
    max_blocks: int = 100
    max_friends: int = 500
    occupation: Optional[str] = None
    playmode: GameMode = GameMode.OSU
    playstyle: List[PlayStyle] = []
    post_count: int = 0
    profile_hue: Optional[int] = None
    profile_order: List[str] = ["me", "recent_activity", "top_ranks", "medals", "historical", "beatmaps", "kudosu"]
    title: Optional[str] = None
    title_url: Optional[str] = None
    twitter: Optional[str] = None
    website: Optional[str] = None
    session_verified: bool = False
    support_level: int = 0
    
    # 关联对象
    country: Country
    cover: Cover
    kudosu: Kudosu
    statistics: Statistics
    statistics_rulesets: dict[str, Statistics]
    
    # 计数信息
    beatmap_playcounts_count: int = 0
    comments_count: int = 0
    favourite_beatmapset_count: int = 0
    follower_count: int = 0
    graveyard_beatmapset_count: int = 0
    guest_beatmapset_count: int = 0
    loved_beatmapset_count: int = 0
    mapping_follower_count: int = 0
    nominated_beatmapset_count: int = 0
    pending_beatmapset_count: int = 0
    ranked_beatmapset_count: int = 0
    ranked_and_approved_beatmapset_count: int = 0
    unranked_beatmapset_count: int = 0
    scores_best_count: int = 0
    scores_first_count: int = 0
    scores_pinned_count: int = 0
    scores_recent_count: int = 0
    
    # 历史数据
    account_history: List[dict] = []
    active_tournament_banner: Optional[dict] = None
    active_tournament_banners: List[dict] = []
    badges: List[dict] = []
    current_season_stats: Optional[dict] = None
    daily_challenge_user_stats: Optional[DailyChallengeStats] = None
    groups: List[dict] = []
    monthly_playcounts: List[MonthlyPlaycount] = []
    page: Page = Page()
    previous_usernames: List[str] = []
    rank_highest: Optional[RankHighest] = None
    rank_history: Optional[RankHistory] = None
    rankHistory: Optional[RankHistory] = None  # 兼容性别名
    replays_watched_counts: List[dict] = []
    team: Optional[Team] = None
    user_achievements: List[UserAchievement] = []


# OAuth 相关模型
class TokenRequest(BaseModel):
    grant_type: str
    username: Optional[str] = None
    password: Optional[str] = None
    refresh_token: Optional[str] = None
    client_id: str
    client_secret: str
    scope: str = "*"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    refresh_token: str
    scope: str = "*"


class UserCreate(BaseModel):
    username: str
    password: str
    email: str
    country_code: str = "CN"
