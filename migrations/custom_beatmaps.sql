-- 自定义谱面系统迁移
-- 创建自定义谱面表，与官方谱面不冲突

-- 自定义谱面集表
CREATE TABLE custom_mapsets (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    creator_id INT NOT NULL,
    title VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
    artist VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
    source VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT '',
    tags TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
    description TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
    status ENUM('pending', 'approved', 'rejected', 'loved') DEFAULT 'pending',
    upload_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_update DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    osz_filename VARCHAR(255) NOT NULL,
    osz_hash CHAR(32) NOT NULL,
    download_count INT DEFAULT 0,
    favourite_count INT DEFAULT 0,
    UNIQUE KEY idx_custom_mapsets_id (id),
    KEY idx_custom_mapsets_creator (creator_id),
    KEY idx_custom_mapsets_status (status),
    KEY idx_custom_mapsets_upload_date (upload_date),
    UNIQUE KEY idx_custom_mapsets_osz_hash (osz_hash)
);

-- 自定义谱面难度表
CREATE TABLE custom_maps (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    mapset_id BIGINT NOT NULL,
    md5 CHAR(32) NOT NULL,
    difficulty_name VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
    filename VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
    mode TINYINT DEFAULT 0 NOT NULL COMMENT '0=osu!, 1=taiko, 2=catch, 3=mania',
    status ENUM('pending', 'approved', 'rejected', 'loved') DEFAULT 'pending',

    -- osu!文件基本信息
    audio_filename VARCHAR(255) DEFAULT '',
    audio_lead_in INT DEFAULT 0,
    preview_time INT DEFAULT -1,
    countdown TINYINT DEFAULT 1,
    sample_set VARCHAR(16) DEFAULT 'Normal',
    stack_leniency DECIMAL(3,2) DEFAULT 0.70,
    letterbox_in_breaks BOOLEAN DEFAULT FALSE,
    story_fire_in_front BOOLEAN DEFAULT TRUE,
    use_skin_sprites BOOLEAN DEFAULT FALSE,
    always_show_playfield BOOLEAN DEFAULT FALSE,
    overlay_position VARCHAR(16) DEFAULT 'NoChange',
    skin_preference VARCHAR(255) DEFAULT '',
    epilepsy_warning BOOLEAN DEFAULT FALSE,
    countdown_offset INT DEFAULT 0,
    special_style BOOLEAN DEFAULT FALSE,
    widescreen_storyboard BOOLEAN DEFAULT FALSE,
    samples_match_playback_rate BOOLEAN DEFAULT FALSE,

    -- 编辑器信息
    distance_spacing DECIMAL(6,3) DEFAULT 1.000,
    beat_divisor TINYINT DEFAULT 4,
    grid_size TINYINT DEFAULT 4,
    timeline_zoom DECIMAL(6,3) DEFAULT 1.000,

    -- 谱面元数据
    title_unicode VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT '',
    artist_unicode VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT '',
    creator VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
    version VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
    source VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT '',
    tags TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
    beatmap_id BIGINT DEFAULT 0,
    beatmapset_id BIGINT DEFAULT 0,

    -- 难度设定
    hp_drain_rate DECIMAL(3,1) DEFAULT 5.0,
    circle_size DECIMAL(3,1) DEFAULT 5.0,
    overall_difficulty DECIMAL(3,1) DEFAULT 5.0,
    approach_rate DECIMAL(3,1) DEFAULT 5.0,
    slider_multiplier DECIMAL(6,3) DEFAULT 1.400,
    slider_tick_rate DECIMAL(3,1) DEFAULT 1.0,

    -- 计算得出的信息
    total_length INT DEFAULT 0 COMMENT '总长度(秒)',
    hit_length INT DEFAULT 0 COMMENT '击打长度(秒)',
    max_combo INT DEFAULT 0,
    bpm DECIMAL(8,3) DEFAULT 0.000,
    star_rating DECIMAL(6,3) DEFAULT 0.000,
    aim_difficulty DECIMAL(6,3) DEFAULT 0.000,
    speed_difficulty DECIMAL(6,3) DEFAULT 0.000,

    -- 统计信息
    plays INT DEFAULT 0,
    passes INT DEFAULT 0,

    -- 时间戳
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY idx_custom_maps_id (id),
    UNIQUE KEY idx_custom_maps_md5 (md5),
    KEY idx_custom_maps_mapset (mapset_id),
    KEY idx_custom_maps_mode (mode),
    KEY idx_custom_maps_status (status),
    KEY idx_custom_maps_creator (creator),
    KEY idx_custom_maps_star_rating (star_rating),
    KEY idx_custom_maps_plays (plays),

    FOREIGN KEY (mapset_id) REFERENCES custom_mapsets(id) ON DELETE CASCADE
);

-- 自定义谱面书签表
CREATE TABLE custom_map_bookmarks (
    user_id INT NOT NULL,
    mapset_id BIGINT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, mapset_id),
    FOREIGN KEY (mapset_id) REFERENCES custom_mapsets(id) ON DELETE CASCADE
);

-- 自定义谱面评分表
CREATE TABLE custom_map_ratings (
    user_id INT NOT NULL,
    map_id BIGINT NOT NULL,
    rating TINYINT NOT NULL CHECK (rating >= 1 AND rating <= 10),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, map_id),
    FOREIGN KEY (map_id) REFERENCES custom_maps(id) ON DELETE CASCADE
);

-- 自定义谱面成绩表 (继承原scores表结构)
CREATE TABLE custom_scores (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    map_id BIGINT NOT NULL,
    map_md5 CHAR(32) NOT NULL,
    user_id INT NOT NULL,
    score INT NOT NULL,
    pp FLOAT(7,3) NOT NULL,
    acc FLOAT(6,3) NOT NULL,
    max_combo INT NOT NULL,
    mods INT NOT NULL,
    n300 INT NOT NULL,
    n100 INT NOT NULL,
    n50 INT NOT NULL,
    nmiss INT NOT NULL,
    ngeki INT NOT NULL,
    nkatu INT NOT NULL,
    grade VARCHAR(2) DEFAULT 'N' NOT NULL,
    status TINYINT NOT NULL COMMENT '0=failed, 1=submitted, 2=best',
    mode TINYINT NOT NULL,
    play_time DATETIME NOT NULL,
    time_elapsed INT NOT NULL,
    client_flags INT NOT NULL,
    perfect BOOLEAN NOT NULL,
    online_checksum CHAR(32) NOT NULL,

    KEY idx_custom_scores_map_id (map_id),
    KEY idx_custom_scores_map_md5 (map_md5),
    KEY idx_custom_scores_user_id (user_id),
    KEY idx_custom_scores_score (score),
    KEY idx_custom_scores_pp (pp),
    KEY idx_custom_scores_mods (mods),
    KEY idx_custom_scores_status (status),
    KEY idx_custom_scores_mode (mode),
    KEY idx_custom_scores_play_time (play_time),
    KEY idx_custom_scores_online_checksum (online_checksum),
    KEY idx_custom_scores_leaderboard (map_md5, status, mode),

    FOREIGN KEY (map_id) REFERENCES custom_maps(id) ON DELETE CASCADE
);

-- 自定义谱面文件存储表 (用于存储.osu文件内容等)
CREATE TABLE custom_map_files (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    map_id BIGINT NOT NULL,
    file_type ENUM('osu', 'audio', 'image', 'video', 'storyboard') NOT NULL,
    filename VARCHAR(255) NOT NULL,
    file_hash CHAR(32) NOT NULL,
    file_size INT NOT NULL,
    mime_type VARCHAR(100) DEFAULT '',
    storage_path VARCHAR(500) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    UNIQUE KEY idx_custom_map_files_id (id),
    KEY idx_custom_map_files_map_id (map_id),
    KEY idx_custom_map_files_type (file_type),
    KEY idx_custom_map_files_hash (file_hash),

    FOREIGN KEY (map_id) REFERENCES custom_maps(id) ON DELETE CASCADE
);

-- 为自定义谱面创建专门的ID生成器，避免与官方ID冲突
-- 自定义谱面ID从1000000开始
ALTER TABLE custom_mapsets AUTO_INCREMENT = 3000000;
ALTER TABLE custom_maps AUTO_INCREMENT = 3000000;

-- 创建触发器来同步mapset信息到maps表
DELIMITER $$

CREATE TRIGGER update_custom_mapset_on_map_change
AFTER UPDATE ON custom_maps
FOR EACH ROW
BEGIN
    IF NEW.status != OLD.status THEN
        UPDATE custom_mapsets
        SET last_update = CURRENT_TIMESTAMP
        WHERE id = NEW.mapset_id;
    END IF;
END$$

DELIMITER ;
