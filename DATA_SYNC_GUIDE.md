# Lazer API 数据同步指南

本指南将帮助您将现有的 bancho.py 数据库数据同步到新的 Lazer API 专用表中。

## 文件说明

1. **`migrations_old/add_missing_fields.sql`** - 创建 Lazer API 专用表结构
2. **`migrations_old/sync_legacy_data.sql`** - 数据同步脚本
3. **`sync_data.py`** - 交互式数据同步工具
4. **`quick_sync.py`** - 快速同步脚本（使用项目配置）

## 使用方法

### 方法一：快速同步（推荐）

如果您已经配置好了项目的数据库连接，可以直接使用快速同步脚本：

```bash
python quick_sync.py
```

此脚本会：
1. 自动读取项目配置中的数据库连接信息
2. 创建 Lazer API 专用表结构
3. 同步现有数据到新表

### 方法二：交互式同步

如果需要使用不同的数据库连接配置：

```bash
python sync_data.py
```

此脚本会：
1. 交互式地询问数据库连接信息
2. 检查必要表是否存在
3. 显示详细的同步过程和结果

### 方法三：手动执行 SQL

如果您熟悉 SQL 操作，可以手动执行：

```bash
# 1. 创建表结构
mysql -u username -p database_name < migrations_old/add_missing_fields.sql

# 2. 同步数据
mysql -u username -p database_name < migrations_old/sync_legacy_data.sql
```

## 同步内容

### 创建的新表

- `lazer_user_profiles` - 用户扩展资料
- `lazer_user_countries` - 用户国家信息
- `lazer_user_kudosu` - 用户 Kudosu 统计
- `lazer_user_counts` - 用户各项计数统计
- `lazer_user_statistics` - 用户游戏统计（按模式）
- `lazer_user_achievements` - 用户成就
- `lazer_oauth_tokens` - OAuth 访问令牌
- 其他相关表...

### 同步的数据

1. **用户基本信息**
   - 从 `users` 表同步基本资料
   - 自动转换时间戳格式
   - 设置合理的默认值

2. **游戏统计**
   - 从 `stats` 表同步各模式的游戏数据
   - 计算命中精度和其他衍生统计

3. **用户成就**
   - 从 `user_achievements` 表同步成就数据（如果存在）

## 注意事项

1. **安全性**
   - 脚本只会创建新表和插入数据
   - 不会修改或删除现有的原始表数据
   - 使用 `ON DUPLICATE KEY UPDATE` 避免重复插入

2. **兼容性**
   - 兼容现有的 bancho.py 数据库结构
   - 支持标准的 osu! 数据格式

3. **性能**
   - 大量数据可能需要较长时间
   - 建议在维护窗口期间执行

## 故障排除

### 常见错误

1. **"Unknown column" 错误**
   ```
   ERROR 1054: Unknown column 'users.is_active' in 'field list'
   ```
   **解决方案**: 确保先执行了 `add_missing_fields.sql` 创建表结构

2. **"Table doesn't exist" 错误**
   ```
   ERROR 1146: Table 'database.users' doesn't exist
   ```
   **解决方案**: 确认数据库中存在 bancho.py 的原始表

3. **连接错误**
   ```
   ERROR 2003: Can't connect to MySQL server
   ```
   **解决方案**: 检查数据库连接配置和权限

### 验证同步结果

同步完成后，可以执行以下查询验证结果：

```sql
-- 检查同步的用户数量
SELECT COUNT(*) FROM lazer_user_profiles;

-- 查看样本数据
SELECT 
    u.id, u.name,
    lup.playmode, lup.is_supporter,
    lus.pp, lus.play_count
FROM users u
LEFT JOIN lazer_user_profiles lup ON u.id = lup.user_id
LEFT JOIN lazer_user_statistics lus ON u.id = lus.user_id AND lus.mode = 'osu'
LIMIT 5;
```

## 支持

如果遇到问题，请：
1. 检查日志文件 `data_sync.log`
2. 确认数据库权限
3. 验证原始表数据完整性
