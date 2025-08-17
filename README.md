# g0v0-server

[English](./README.en.md) | 简体中文

这是一个使用 FastAPI + MySQL + Redis 实现的 osu! API 模拟服务器，支持 osu! API v1, v2 和 osu!lazer 的绝大部分功能。

## 功能特性

- **OAuth 2.0 认证**: 支持密码流和刷新令牌流
- **用户数据管理**: 完整的用户信息、统计数据、成就等
- **多游戏模式支持**: osu! (RX, AP), taiko (RX), catch (RX), mania
- **数据库持久化**: MySQL 存储用户数据
- **缓存支持**: Redis 缓存令牌和会话信息
- **多种存储后端**: 支持本地存储、Cloudflare R2、AWS S3
- **容器化部署**: Docker 和 Docker Compose 支持

## 快速开始

### 使用 Docker Compose (推荐)

1. 克隆项目
```bash
git clone https://github.com/GooGuTeam/g0v0-server.git
cd g0v0-server
```

2. 创建 `.env` 文件

请参考下方的服务器配置修改 .env 文件

```bash
cp .env.example .env
```

3. 启动服务
```bash
# 标准服务器
docker-compose -f docker-compose.yml up -d
# 启用 osu!RX 和 osu!AP 模式 （偏偏要上班 pp 算法）
docker-compose -f docker-compose-osurx.yml up -d
```

4. 通过游戏连接服务器

使用[自定义的 osu!lazer 客户端](https://github.com/GooGuTeam/osu)，或者使用 [LazerAuthlibInjection](https://github.com/MingxuanGame/LazerAuthlibInjection)，修改服务器设置为服务器的 IP

## 环境变量配置

### 数据库设置
| 变量名 | 描述 | 默认值 |
|--------|------|--------|
| `MYSQL_HOST` | MySQL 主机地址 | `localhost` |
| `MYSQL_PORT` | MySQL 端口 | `3306` |
| `MYSQL_DATABASE` | MySQL 数据库名 | `osu_api` |
| `MYSQL_USER` | MySQL 用户名 | `osu_api` |
| `MYSQL_PASSWORD` | MySQL 密码 | `password` |
| `MYSQL_ROOT_PASSWORD` | MySQL root 密码 | `password` |
| `REDIS_URL` | Redis 连接字符串 | `redis://127.0.0.1:6379/0` |

### JWT 设置
| 变量名 | 描述 | 默认值 |
|--------|------|--------|
| `JWT_SECRET_KEY` | JWT 签名密钥 | `your_jwt_secret_here` |
| `ALGORITHM` | JWT 算法 | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 访问令牌过期时间（分钟） | `1440` |

### 服务器设置
| 变量名 | 描述 | 默认值 |
|--------|------|--------|
| `HOST` | 服务器监听地址 | `0.0.0.0` |
| `PORT` | 服务器监听端口 | `8000` |
| `DEBUG` | 调试模式 | `false` |
| `SERVER_URL` | 服务器 URL | `http://localhost:8000` |
| `CORS_URLS` | 额外的 CORS 允许的域名列表 (JSON 格式) | `[]` |
| `FRONTEND_URL` | 前端 URL，当访问从游戏打开的 URL 时会重定向到这个 URL，为空表示不重定向 | `(null)` |

### OAuth 设置
| 变量名 | 描述 | 默认值 |
|--------|------|--------|
| `OSU_CLIENT_ID` | OAuth 客户端 ID | `5` |
| `OSU_CLIENT_SECRET` | OAuth 客户端密钥 | `FGc9GAtyHzeQDshWP5Ah7dega8hJACAJpQtw6OXk` |
| `OSU_WEB_CLIENT_ID` | Web OAuth 客户端 ID | `6` |
| `OSU_WEB_CLIENT_SECRET` | Web OAuth 客户端密钥 | `your_osu_web_client_secret_here`

### SignalR 服务器设置
| 变量名 | 描述 | 默认值 |
|--------|------|--------|
| `SIGNALR_NEGOTIATE_TIMEOUT` | SignalR 协商超时时间（秒） | `30` |
| `SIGNALR_PING_INTERVAL` | SignalR ping 间隔（秒） | `15` |

### Fetcher 设置

Fetcher 用于从 osu! 官方 API 获取数据，使用 osu! 官方 API 的 OAuth 2.0 认证

| 变量名 | 描述 | 默认值 |
|--------|------|--------|
| `FETCHER_CLIENT_ID` | Fetcher 客户端 ID | `""` |
| `FETCHER_CLIENT_SECRET` | Fetcher 客户端密钥 | `""` |
| `FETCHER_SCOPES` | Fetcher 权限范围 | `public` |

### 日志设置
| 变量名 | 描述 | 默认值 |
|--------|------|--------|
| `LOG_LEVEL` | 日志级别 | `INFO` |

### Sentry 设置
| 变量名 | 描述 | 默认值 |
|--------|------|--------|
| `SENTRY_DSN` | Sentry DSN，为空不启用 Sentry | `(null)` |

### 游戏设置
| 变量名 | 描述 | 默认值 |
|--------|------|--------|
| `ENABLE_RX` | 启用 RX mod 统计数据 | `false` |
| `ENABLE_AP` | 启用 AP mod 统计数据 | `false` |
| `ENABLE_ALL_MODS_PP` | 启用所有 Mod 的 PP 计算 | `false` |
| `ENABLE_SUPPORTER_FOR_ALL_USERS` | 启用所有新注册用户的支持者状态 | `false` |
| `ENABLE_ALL_BEATMAP_LEADERBOARD` | 启用所有谱面的排行榜 | `false` |
| `ENABLE_ALL_BEATMAP_PP` | 允许任何谱面获得 PP | `false` |
| `SUSPICIOUS_SCORE_CHECK` | 启用可疑分数检查（star>25&acc<80 或 pp>2300） | `true` |
| `SEASONAL_BACKGROUNDS` | 季节背景图 URL 列表 | `[]` |
| `BANNED_NAME` | 禁止使用的用户名列表 | `["mrekk", "vaxei", "btmc", "cookiezi", "peppy", "saragi", "chocomint"]` |

### 存储服务设置

用于存储回放文件、头像等静态资源。

| 变量名 | 描述 | 默认值 |
|--------|------|--------|
| `STORAGE_SERVICE` | 存储服务类型：`local`、`r2`、`s3` | `local` |
| `STORAGE_SETTINGS` | 存储服务配置 (JSON 格式)，配置见下 | `{"local_storage_path": "./storage"}` |

## 存储服务配置

### 本地存储 (推荐用于开发环境)

本地存储将文件保存在服务器的本地文件系统中，适合开发和小规模部署。

```bash
STORAGE_SERVICE="local"
STORAGE_SETTINGS='{"local_storage_path": "./storage"}'
```

### Cloudflare R2 存储 (推荐用于生产环境)

```bash
STORAGE_SERVICE="r2"
STORAGE_SETTINGS='{
  "r2_account_id": "your_cloudflare_account_id",
  "r2_access_key_id": "your_r2_access_key_id",
  "r2_secret_access_key": "your_r2_secret_access_key",
  "r2_bucket_name": "your_bucket_name",
  "r2_public_url_base": "https://your-custom-domain.com"
}'
```

### AWS S3 存储

```bash
STORAGE_SERVICE="s3"
STORAGE_SETTINGS='{
  "s3_access_key_id": "your_aws_access_key_id",
  "s3_secret_access_key": "your_aws_secret_access_key",
  "s3_bucket_name": "your_s3_bucket_name",
  "s3_region_name": "us-east-1",
  "s3_public_url_base": "https://your-custom-domain.com"
}'
```

> **注意**: 在生产环境中，请务必更改默认的密钥和密码！

### 更新数据库

参考[数据库迁移指南](https://github.com/GooGuTeam/g0v0-server/wiki/Migrate-Database)

## 许可证

MIT License

## 贡献

项目目前处于快速迭代状态，欢迎提交 Issue 和 Pull Request！

## 参与讨论

- QQ 群：`1059561526`
- Discord: https://discord.gg/AhzJXXWYfF
