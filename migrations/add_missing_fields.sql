-- Lazer API 专用数据表创建脚本
-- 基于真实 osu! API 返回数据设计的表结构
-- 完全不修改 bancho.py 原有表结构，创建全新的 lazer 专用表

-- ============================================
-- Lazer API 专用扩展表
-- ============================================

-- Lazer 用户扩展信息表
CREATE TABLE IF NOT EXISTS lazer_user_profiles (
    user_id INT PRIMARY KEY COMMENT '关联 users.id',
    
    -- 基本状态字段
    is_active TINYINT(1) DEFAULT 1 COMMENT '用户是否激活',
    is_bot TINYINT(1) DEFAULT 0 COMMENT '是否为机器人账户',
    is_deleted TINYINT(1) DEFAULT 0 COMMENT '是否已删除',
    is_online TINYINT(1) DEFAULT 1 COMMENT '是否在线',
    is_supporter TINYINT(1) DEFAULT 0 COMMENT '是否为支持者',
    is_restricted TINYINT(1) DEFAULT 0 COMMENT '是否被限制',
    session_verified TINYINT(1) DEFAULT 0 COMMENT '会话是否已验证',
    has_supported TINYINT(1) DEFAULT 0 COMMENT '是否曾经支持过',
    pm_friends_only TINYINT(1) DEFAULT 0 COMMENT '是否只接受好友私信',
    
    -- 基本资料字段
    default_group VARCHAR(50) DEFAULT 'default' COMMENT '默认用户组',
    last_visit DATETIME NULL COMMENT '最后访问时间',
    join_date DATETIME NULL COMMENT '加入日期',
    profile_colour VARCHAR(7) NULL COMMENT '个人资料颜色',
    profile_hue INT NULL COMMENT '个人资料色调',
    
    -- 社交媒体和个人资料字段
    avatar_url VARCHAR(500) NULL COMMENT '头像URL',
    cover_url VARCHAR(500) NULL COMMENT '封面URL',
    discord VARCHAR(100) NULL COMMENT 'Discord用户名',
    twitter VARCHAR(100) NULL COMMENT 'Twitter用户名',
    website VARCHAR(500) NULL COMMENT '个人网站',
    title VARCHAR(100) NULL COMMENT '用户称号',
    title_url VARCHAR(500) NULL COMMENT '称号链接',
    interests TEXT NULL COMMENT '兴趣爱好',
    location VARCHAR(100) NULL COMMENT '地理位置',
    occupation VARCHAR(100) NULL COMMENT '职业',
    
    -- 游戏相关字段
    playmode VARCHAR(10) DEFAULT 'osu' COMMENT '主要游戏模式',
    support_level INT DEFAULT 0 COMMENT '支持者等级',
    max_blocks INT DEFAULT 100 COMMENT '最大屏蔽数量',
    max_friends INT DEFAULT 500 COMMENT '最大好友数量',
    post_count INT DEFAULT 0 COMMENT '帖子数量',
    
    -- 页面内容
    page_html TEXT NULL COMMENT '个人页面HTML',
    page_raw TEXT NULL COMMENT '个人页面原始内容',
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Lazer API 用户扩展资料表';

-- 用户封面信息表
CREATE TABLE IF NOT EXISTS lazer_user_covers (
    user_id INT PRIMARY KEY COMMENT '关联 users.id',
    custom_url VARCHAR(500) NULL COMMENT '自定义封面URL',
    url VARCHAR(500) NULL COMMENT '封面URL',
    cover_id INT NULL COMMENT '封面ID',
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户封面信息表';

-- 用户国家信息表
CREATE TABLE IF NOT EXISTS lazer_user_countries (
    user_id INT PRIMARY KEY COMMENT '关联 users.id',
    code VARCHAR(2) NOT NULL COMMENT '国家代码',
    name VARCHAR(100) NOT NULL COMMENT '国家名称',
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户国家信息表';

-- 用户 Kudosu 表
CREATE TABLE IF NOT EXISTS lazer_user_kudosu (
    user_id INT PRIMARY KEY COMMENT '关联 users.id',
    available INT DEFAULT 0 COMMENT '可用 Kudosu',
    total INT DEFAULT 0 COMMENT '总 Kudosu',
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户 Kudosu 表';

-- 用户统计计数表
CREATE TABLE IF NOT EXISTS lazer_user_counts (
    user_id INT PRIMARY KEY COMMENT '关联 users.id',
    
    -- 统计计数字段
    beatmap_playcounts_count INT DEFAULT 0 COMMENT '谱面游玩次数统计',
    comments_count INT DEFAULT 0 COMMENT '评论数量',
    favourite_beatmapset_count INT DEFAULT 0 COMMENT '收藏谱面集数量',
    follower_count INT DEFAULT 0 COMMENT '关注者数量',
    graveyard_beatmapset_count INT DEFAULT 0 COMMENT '坟场谱面集数量',
    guest_beatmapset_count INT DEFAULT 0 COMMENT '客串谱面集数量',
    loved_beatmapset_count INT DEFAULT 0 COMMENT '被喜爱谱面集数量',
    mapping_follower_count INT DEFAULT 0 COMMENT '作图关注者数量',
    nominated_beatmapset_count INT DEFAULT 0 COMMENT '提名谱面集数量',
    pending_beatmapset_count INT DEFAULT 0 COMMENT '待审核谱面集数量',
    ranked_beatmapset_count INT DEFAULT 0 COMMENT 'Ranked谱面集数量',
    ranked_and_approved_beatmapset_count INT DEFAULT 0 COMMENT 'Ranked+Approved谱面集数量',
    unranked_beatmapset_count INT DEFAULT 0 COMMENT '未Ranked谱面集数量',
    scores_best_count INT DEFAULT 0 COMMENT '最佳成绩数量',
    scores_first_count INT DEFAULT 0 COMMENT '第一名成绩数量',
    scores_pinned_count INT DEFAULT 0 COMMENT '置顶成绩数量',
    scores_recent_count INT DEFAULT 0 COMMENT '最近成绩数量',
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Lazer API 用户统计计数表';

-- 用户游戏风格表 (替代 playstyle JSON)
CREATE TABLE IF NOT EXISTS lazer_user_playstyles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL COMMENT '关联 users.id',
    style VARCHAR(50) NOT NULL COMMENT '游戏风格: mouse, keyboard, tablet, touch',
    
    INDEX idx_user_id (user_id),
    UNIQUE KEY unique_user_style (user_id, style),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户游戏风格表';

-- 用户个人资料显示顺序表 (替代 profile_order JSON)
CREATE TABLE IF NOT EXISTS lazer_user_profile_sections (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL COMMENT '关联 users.id',
    section_name VARCHAR(50) NOT NULL COMMENT '部分名称',
    display_order INT DEFAULT 0 COMMENT '显示顺序',
    
    INDEX idx_user_id (user_id),
    INDEX idx_order (user_id, display_order),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户个人资料显示顺序表';

-- 用户账户历史表 (替代 account_history JSON)
CREATE TABLE IF NOT EXISTS lazer_user_account_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL COMMENT '关联 users.id',
    event_type VARCHAR(50) NOT NULL COMMENT '事件类型',
    description TEXT COMMENT '事件描述',
    length INT COMMENT '持续时间(秒)',
    permanent TINYINT(1) DEFAULT 0 COMMENT '是否永久',
    event_time DATETIME NOT NULL COMMENT '事件时间',
    
    INDEX idx_user_id (user_id),
    INDEX idx_event_time (event_time),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户账户历史表';

-- 用户历史用户名表 (替代 previous_usernames JSON)
CREATE TABLE IF NOT EXISTS lazer_user_previous_usernames (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL COMMENT '关联 users.id',
    username VARCHAR(32) NOT NULL COMMENT '历史用户名',
    changed_at DATETIME NOT NULL COMMENT '更改时间',
    
    INDEX idx_user_id (user_id),
    INDEX idx_changed_at (changed_at),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户历史用户名表';

-- 用户月度游戏次数表 (替代 monthly_playcounts JSON)
CREATE TABLE IF NOT EXISTS lazer_user_monthly_playcounts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL COMMENT '关联 users.id',
    start_date DATE NOT NULL COMMENT '月份开始日期',
    play_count INT DEFAULT 0 COMMENT '游戏次数',
    
    INDEX idx_user_id (user_id),
    INDEX idx_start_date (start_date),
    UNIQUE KEY unique_user_month (user_id, start_date),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户月度游戏次数表';

-- 用户最高排名表 (rank_highest)
CREATE TABLE IF NOT EXISTS lazer_user_rank_highest (
    user_id INT PRIMARY KEY COMMENT '关联 users.id',
    rank_position INT NOT NULL COMMENT '最高排名位置',
    updated_at DATETIME NOT NULL COMMENT '更新时间',
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户最高排名表';

-- ============================================
-- OAuth 令牌表 (Lazer API 专用)
-- ============================================
CREATE TABLE IF NOT EXISTS lazer_oauth_tokens (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    access_token VARCHAR(255) NOT NULL,
    refresh_token VARCHAR(255) NOT NULL,
    expires_at DATETIME NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    INDEX idx_access_token (access_token),
    INDEX idx_refresh_token (refresh_token),
    INDEX idx_expires_at (expires_at),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Lazer API OAuth访问令牌表';

-- ============================================
-- 用户统计数据表 (基于真实 API 数据结构)
-- ============================================

-- 用户主要统计表 (statistics 字段)
CREATE TABLE IF NOT EXISTS lazer_user_statistics (
    user_id INT NOT NULL,
    mode VARCHAR(10) NOT NULL DEFAULT 'osu' COMMENT '游戏模式: osu, taiko, fruits, mania',
    
    -- 基本命中统计
    count_100 INT DEFAULT 0 COMMENT '100分命中数',
    count_300 INT DEFAULT 0 COMMENT '300分命中数',
    count_50 INT DEFAULT 0 COMMENT '50分命中数',
    count_miss INT DEFAULT 0 COMMENT 'Miss数',
    
    -- 等级信息
    level_current INT DEFAULT 1 COMMENT '当前等级',
    level_progress INT DEFAULT 0 COMMENT '等级进度',
    
    -- 排名信息
    global_rank INT NULL COMMENT '全球排名',
    global_rank_exp INT NULL COMMENT '全球排名(实验性)',
    country_rank INT NULL COMMENT '国家/地区排名',
    
    -- PP 和分数
    pp DECIMAL(10,2) DEFAULT 0.00 COMMENT 'Performance Points',
    pp_exp DECIMAL(10,2) DEFAULT 0.00 COMMENT 'PP(实验性)',
    ranked_score BIGINT DEFAULT 0 COMMENT 'Ranked分数',
    hit_accuracy DECIMAL(5,2) DEFAULT 0.00 COMMENT '命中精度',
    total_score BIGINT DEFAULT 0 COMMENT '总分数',
    total_hits BIGINT DEFAULT 0 COMMENT '总命中数',
    maximum_combo INT DEFAULT 0 COMMENT '最大连击',
    
    -- 游戏统计
    play_count INT DEFAULT 0 COMMENT '游戏次数',
    play_time INT DEFAULT 0 COMMENT '游戏时间(秒)',
    replays_watched_by_others INT DEFAULT 0 COMMENT '被观看的Replay次数',
    is_ranked TINYINT(1) DEFAULT 0 COMMENT '是否有排名',
    
    -- 成绩等级计数 (grade_counts)
    grade_ss INT DEFAULT 0 COMMENT 'SS等级数',
    grade_ssh INT DEFAULT 0 COMMENT 'SSH等级数',
    grade_s INT DEFAULT 0 COMMENT 'S等级数',
    grade_sh INT DEFAULT 0 COMMENT 'SH等级数',
    grade_a INT DEFAULT 0 COMMENT 'A等级数',
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    PRIMARY KEY (user_id, mode),
    INDEX idx_mode (mode),
    INDEX idx_global_rank (global_rank),
    INDEX idx_country_rank (country_rank),
    INDEX idx_pp (pp),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Lazer API 用户游戏统计表';

-- 每日挑战用户统计表 (daily_challenge_user_stats)
CREATE TABLE IF NOT EXISTS lazer_daily_challenge_stats (
    user_id INT PRIMARY KEY COMMENT '关联 users.id',
    daily_streak_best INT DEFAULT 0 COMMENT '最佳每日连击',
    daily_streak_current INT DEFAULT 0 COMMENT '当前每日连击',
    last_update DATE NULL COMMENT '最后更新日期',
    last_weekly_streak DATE NULL COMMENT '最后周连击日期',
    playcount INT DEFAULT 0 COMMENT '游戏次数',
    top_10p_placements INT DEFAULT 0 COMMENT 'Top 10% 位置数',
    top_50p_placements INT DEFAULT 0 COMMENT 'Top 50% 位置数',
    weekly_streak_best INT DEFAULT 0 COMMENT '最佳周连击',
    weekly_streak_current INT DEFAULT 0 COMMENT '当前周连击',
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='每日挑战用户统计表';

-- 用户团队信息表 (team 字段)
CREATE TABLE IF NOT EXISTS lazer_user_teams (
    user_id INT PRIMARY KEY COMMENT '关联 users.id',
    team_id INT NOT NULL COMMENT '团队ID',
    team_name VARCHAR(100) NOT NULL COMMENT '团队名称',
    team_short_name VARCHAR(10) NOT NULL COMMENT '团队简称',
    flag_url VARCHAR(500) NULL COMMENT '团队旗帜URL',
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户团队信息表';

-- 用户成就表 (user_achievements)
CREATE TABLE IF NOT EXISTS lazer_user_achievements (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL COMMENT '关联 users.id',
    achievement_id INT NOT NULL COMMENT '成就ID',
    achieved_at DATETIME NOT NULL COMMENT '获得时间',
    
    INDEX idx_user_id (user_id),
    INDEX idx_achievement_id (achievement_id),
    INDEX idx_achieved_at (achieved_at),
    UNIQUE KEY unique_user_achievement (user_id, achievement_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户成就表';

-- 用户排名历史表 (rank_history)
CREATE TABLE IF NOT EXISTS lazer_user_rank_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL COMMENT '关联 users.id',
    mode VARCHAR(10) NOT NULL DEFAULT 'osu' COMMENT '游戏模式',
    day_offset INT NOT NULL COMMENT '天数偏移量(从某个基准日期开始)',
    rank_position INT NOT NULL COMMENT '排名位置',
    
    INDEX idx_user_mode (user_id, mode),
    INDEX idx_day_offset (day_offset),
    UNIQUE KEY unique_user_mode_day (user_id, mode, day_offset),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户排名历史表';

-- Replay 观看次数表 (replays_watched_counts)
CREATE TABLE IF NOT EXISTS lazer_user_replays_watched (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL COMMENT '关联 users.id',
    start_date DATE NOT NULL COMMENT '开始日期',
    count INT DEFAULT 0 COMMENT '观看次数',
    
    INDEX idx_user_id (user_id),
    INDEX idx_start_date (start_date),
    UNIQUE KEY unique_user_date (user_id, start_date),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户Replay观看次数表';

-- 用户徽章表 (badges)
CREATE TABLE IF NOT EXISTS lazer_user_badges (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL COMMENT '关联 users.id',
    badge_id INT NOT NULL COMMENT '徽章ID',
    awarded_at DATETIME NULL COMMENT '授予时间',
    description TEXT NULL COMMENT '徽章描述',
    image_url VARCHAR(500) NULL COMMENT '徽章图片URL',
    url VARCHAR(500) NULL COMMENT '徽章链接',
    
    INDEX idx_user_id (user_id),
    INDEX idx_badge_id (badge_id),
    UNIQUE KEY unique_user_badge (user_id, badge_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户徽章表';

-- 用户组表 (groups)
CREATE TABLE IF NOT EXISTS lazer_user_groups (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL COMMENT '关联 users.id',
    group_id INT NOT NULL COMMENT '用户组ID',
    group_name VARCHAR(100) NOT NULL COMMENT '用户组名称',
    group_identifier VARCHAR(50) NULL COMMENT '用户组标识符',
    colour VARCHAR(7) NULL COMMENT '用户组颜色',
    is_probationary TINYINT(1) DEFAULT 0 COMMENT '是否为试用期',
    has_listing TINYINT(1) DEFAULT 1 COMMENT '是否显示在列表中',
    has_playmodes TINYINT(1) DEFAULT 0 COMMENT '是否有游戏模式',
    
    INDEX idx_user_id (user_id),
    INDEX idx_group_id (group_id),
    UNIQUE KEY unique_user_group (user_id, group_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户组表';

-- 锦标赛横幅表 (active_tournament_banners)
CREATE TABLE IF NOT EXISTS lazer_user_tournament_banners (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL COMMENT '关联 users.id',
    tournament_id INT NOT NULL COMMENT '锦标赛ID',
    image_url VARCHAR(500) NOT NULL COMMENT '横幅图片URL',
    is_active TINYINT(1) DEFAULT 1 COMMENT '是否为当前活跃横幅',
    
    INDEX idx_user_id (user_id),
    INDEX idx_tournament_id (tournament_id),
    INDEX idx_is_active (is_active),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户锦标赛横幅表';

-- ============================================
-- 占位表 (未来功能扩展用)
-- ============================================

-- 当前赛季统计占位表
CREATE TABLE IF NOT EXISTS lazer_current_season_stats (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL COMMENT '关联 users.id',
    season_id VARCHAR(50) NOT NULL COMMENT '赛季ID',
    data_placeholder TEXT COMMENT '赛季数据占位',
    
    INDEX idx_user_id (user_id),
    INDEX idx_season_id (season_id),
    UNIQUE KEY unique_user_season (user_id, season_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='当前赛季统计占位表';

-- 其他功能占位表
CREATE TABLE IF NOT EXISTS lazer_feature_placeholder (
    id INT AUTO_INCREMENT PRIMARY KEY,
    feature_type VARCHAR(50) NOT NULL COMMENT '功能类型',
    entity_id INT NOT NULL COMMENT '实体ID',
    data_placeholder TEXT COMMENT '功能数据占位',
    
    INDEX idx_feature_type (feature_type),
    INDEX idx_entity_id (entity_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='功能扩展占位表';
