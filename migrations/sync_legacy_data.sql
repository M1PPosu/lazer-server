-- Lazer API 数据同步脚本
-- 从现有的 bancho.py 表结构同步数据到新的 lazer 专用表
-- 执行此脚本前请确保已执行 add_missing_fields.sql

-- ============================================
-- 同步用户基本资料数据
-- ============================================

-- 同步用户扩展资料
INSERT INTO lazer_user_profiles (
    user_id,
    is_active,
    is_bot,
    is_deleted,
    is_online,
    is_supporter,
    is_restricted,
    session_verified,
    has_supported,
    pm_friends_only,
    default_group,
    last_visit,
    join_date,
    profile_colour,
    profile_hue,
    avatar_url,
    cover_url,
    discord,
    twitter,
    website,
    title,
    title_url,
    interests,
    location,
    occupation,
    playmode,
    support_level,
    max_blocks,
    max_friends,
    post_count,
    page_html,
    page_raw
)
SELECT 
    u.id as user_id,
    -- 基本状态字段 (使用默认值，因为原表没有这些字段)
    1 as is_active,
    CASE WHEN u.name = 'BanchoBot' THEN 1 ELSE 0 END as is_bot,
    0 as is_deleted,
    1 as is_online,
    CASE WHEN u.donor_end > UNIX_TIMESTAMP() THEN 1 ELSE 0 END as is_supporter,
    CASE WHEN (u.priv & 1) = 0 THEN 1 ELSE 0 END as is_restricted,
    0 as session_verified,
    CASE WHEN u.donor_end > 0 THEN 1 ELSE 0 END as has_supported,
    0 as pm_friends_only,
    
    -- 基本资料字段
    'default' as default_group,
    CASE WHEN u.latest_activity > 0 THEN FROM_UNIXTIME(u.latest_activity) ELSE NULL END as last_visit,
    CASE WHEN u.creation_time > 0 THEN FROM_UNIXTIME(u.creation_time) ELSE NULL END as join_date,
    NULL as profile_colour,
    NULL as profile_hue,
    
    -- 社交媒体和个人资料字段 (使用默认值)
    CONCAT('https://a.ppy.sh/', u.id) as avatar_url,
    CONCAT('https://assets.ppy.sh/user-profile-covers/banners/', u.id, '.jpg') as cover_url,
    NULL as discord,
    NULL as twitter,
    NULL as website,
    u.custom_badge_name as title,
    NULL as title_url,
    NULL as interests,
    CASE WHEN u.country != 'xx' THEN u.country ELSE NULL END as location,
    NULL as occupation,
    
    -- 游戏相关字段
    CASE u.preferred_mode 
        WHEN 0 THEN 'osu'
        WHEN 1 THEN 'taiko' 
        WHEN 2 THEN 'fruits'
        WHEN 3 THEN 'mania'
        ELSE 'osu'
    END as playmode,
    CASE WHEN u.donor_end > UNIX_TIMESTAMP() THEN 1 ELSE 0 END as support_level,
    100 as max_blocks,
    500 as max_friends,
    0 as post_count,
    
    -- 页面内容
    u.userpage_content as page_html,
    u.userpage_content as page_raw
    
FROM users u
ON DUPLICATE KEY UPDATE
    last_visit = VALUES(last_visit),
    join_date = VALUES(join_date),
    is_supporter = VALUES(is_supporter),
    is_restricted = VALUES(is_restricted),
    has_supported = VALUES(has_supported),
    title = VALUES(title),
    location = VALUES(location),
    playmode = VALUES(playmode),
    support_level = VALUES(support_level),
    page_html = VALUES(page_html),
    page_raw = VALUES(page_raw);

-- 同步用户国家信息
INSERT INTO lazer_user_countries (
    user_id,
    code,
    name
)
SELECT 
    u.id as user_id,
    UPPER(u.country) as code,
    CASE UPPER(u.country)
        WHEN 'CN' THEN 'China'
        WHEN 'US' THEN 'United States'
        WHEN 'JP' THEN 'Japan'
        WHEN 'KR' THEN 'South Korea'
        WHEN 'CA' THEN 'Canada'
        WHEN 'GB' THEN 'United Kingdom'
        WHEN 'DE' THEN 'Germany'
        WHEN 'FR' THEN 'France'
        WHEN 'AU' THEN 'Australia'
        WHEN 'RU' THEN 'Russia'
        ELSE 'Unknown'
    END as name
FROM users u
WHERE u.country IS NOT NULL AND u.country != 'xx'
ON DUPLICATE KEY UPDATE
    code = VALUES(code),
    name = VALUES(name);

-- 同步用户 Kudosu (使用默认值)
INSERT INTO lazer_user_kudosu (
    user_id,
    available,
    total
)
SELECT 
    u.id as user_id,
    0 as available,
    0 as total
FROM users u
ON DUPLICATE KEY UPDATE
    available = VALUES(available),
    total = VALUES(total);

-- 同步用户统计计数 (使用默认值)
INSERT INTO lazer_user_counts (
    user_id,
    beatmap_playcounts_count,
    comments_count,
    favourite_beatmapset_count,
    follower_count,
    graveyard_beatmapset_count,
    guest_beatmapset_count,
    loved_beatmapset_count,
    mapping_follower_count,
    nominated_beatmapset_count,
    pending_beatmapset_count,
    ranked_beatmapset_count,
    ranked_and_approved_beatmapset_count,
    unranked_beatmapset_count,
    scores_best_count,
    scores_first_count,
    scores_pinned_count,
    scores_recent_count
)
SELECT 
    u.id as user_id,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
FROM users u
ON DUPLICATE KEY UPDATE
    user_id = VALUES(user_id);

-- ============================================
-- 同步游戏统计数据
-- ============================================

-- 从 stats 表同步用户统计数据到 lazer_user_statistics
INSERT INTO lazer_user_statistics (
    user_id,
    mode,
    count_100,
    count_300,
    count_50,
    count_miss,
    level_current,
    level_progress,
    global_rank,
    country_rank,
    pp,
    ranked_score,
    hit_accuracy,
    total_score,
    total_hits,
    maximum_combo,
    play_count,
    play_time,
    replays_watched_by_others,
    is_ranked,
    grade_ss,
    grade_ssh,
    grade_s,
    grade_sh,
    grade_a
)
SELECT 
    s.id as user_id,
    CASE s.mode 
        WHEN 0 THEN 'osu'
        WHEN 1 THEN 'taiko'
        WHEN 2 THEN 'fruits'
        WHEN 3 THEN 'mania'
        ELSE 'osu'
    END as mode,
    
    -- 基本命中统计
    s.n100 as count_100,
    s.n300 as count_300,
    s.n50 as count_50,
    s.nmiss as count_miss,
    
    -- 等级信息
    1 as level_current,
    0 as level_progress,
    
    -- 排名信息
    NULL as global_rank,
    NULL as country_rank,
    
    -- PP 和分数
    s.pp as pp,
    s.rscore as ranked_score,
    CASE WHEN (s.n300 + s.n100 + s.n50 + s.nmiss) > 0 
         THEN ROUND((s.n300 * 300 + s.n100 * 100 + s.n50 * 50) / ((s.n300 + s.n100 + s.n50 + s.nmiss) * 300) * 100, 2)
         ELSE 0.00 
    END as hit_accuracy,
    s.tscore as total_score,
    (s.n300 + s.n100 + s.n50) as total_hits,
    s.max_combo as maximum_combo,
    
    -- 游戏统计
    s.plays as play_count,
    s.playtime as play_time,
    0 as replays_watched_by_others,
    CASE WHEN s.pp > 0 THEN 1 ELSE 0 END as is_ranked,
    
    -- 成绩等级计数
    0 as grade_ss,
    0 as grade_ssh,
    0 as grade_s,
    0 as grade_sh,
    0 as grade_a

FROM stats s
WHERE EXISTS (SELECT 1 FROM users u WHERE u.id = s.id)
ON DUPLICATE KEY UPDATE
    count_100 = VALUES(count_100),
    count_300 = VALUES(count_300),
    count_50 = VALUES(count_50),
    count_miss = VALUES(count_miss),
    pp = VALUES(pp),
    ranked_score = VALUES(ranked_score),
    hit_accuracy = VALUES(hit_accuracy),
    total_score = VALUES(total_score),
    total_hits = VALUES(total_hits),
    maximum_combo = VALUES(maximum_combo),
    play_count = VALUES(play_count),
    play_time = VALUES(play_time),
    is_ranked = VALUES(is_ranked);

-- ============================================
-- 同步用户成就数据
-- ============================================

-- 从 user_achievements 表同步数据（如果存在的话）
INSERT IGNORE INTO lazer_user_achievements (
    user_id,
    achievement_id,
    achieved_at
)
SELECT 
    ua.userid as user_id,
    ua.achid as achievement_id,
    NOW() as achieved_at  -- 使用当前时间作为获得时间
FROM user_achievements ua
WHERE EXISTS (SELECT 1 FROM users u WHERE u.id = ua.userid);

-- ============================================
-- 创建基础 OAuth 令牌记录（如果需要的话）
-- ============================================

-- 注意: OAuth 令牌通常在用户登录时动态创建，这里不需要预先填充

-- ============================================
-- 同步完成提示
-- ============================================

-- 显示同步统计信息
SELECT 
    'lazer_user_profiles' as table_name,
    COUNT(*) as synced_records
FROM lazer_user_profiles
UNION ALL
SELECT 
    'lazer_user_countries' as table_name,
    COUNT(*) as synced_records
FROM lazer_user_countries
UNION ALL
SELECT 
    'lazer_user_statistics' as table_name,
    COUNT(*) as synced_records
FROM lazer_user_statistics
UNION ALL
SELECT 
    'lazer_user_achievements' as table_name,
    COUNT(*) as synced_records
FROM lazer_user_achievements;

-- 显示一些样本数据
SELECT 
    u.id,
    u.name,
    lup.is_supporter,
    lup.playmode,
    luc.code as country_code,
    lus.pp,
    lus.play_count
FROM users u
LEFT JOIN lazer_user_profiles lup ON u.id = lup.user_id
LEFT JOIN lazer_user_countries luc ON u.id = luc.user_id
LEFT JOIN lazer_user_statistics lus ON u.id = lus.user_id AND lus.mode = 'osu'
ORDER BY u.id
LIMIT 10;
