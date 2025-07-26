-- 创建迁移日志表（如果不存在）
CREATE TABLE IF NOT EXISTS `migration_logs` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `version` VARCHAR(50) NOT NULL,
    `description` VARCHAR(255) NOT NULL,
    `timestamp` DATETIME NOT NULL
);

-- 向 lazer_user_statistics 表添加缺失的字段
ALTER TABLE `lazer_user_statistics` 
ADD COLUMN IF NOT EXISTS `rank_highest` INT NULL COMMENT '最高排名' AFTER `grade_a`,
ADD COLUMN IF NOT EXISTS `rank_highest_updated_at` DATETIME NULL COMMENT '最高排名更新时间' AFTER `rank_highest`;

-- 更新日志
INSERT INTO `migration_logs` (`version`, `description`, `timestamp`)
VALUES ('20250719', '向 lazer_user_statistics 表添加缺失的字段', NOW());
