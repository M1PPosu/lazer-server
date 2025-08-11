# osu! API 模拟服务器

这是一个使用 FastAPI + MySQL + Redis 实现的 osu! API 模拟服务器，提供了完整的用户认证和数据管理功能。

## 功能特性

- **OAuth 2.0 认证**: 支持密码流和刷新令牌流
- **用户数据管理**: 完整的用户信息、统计数据、成就等
- **多游戏模式支持**: osu! (osu!rx, osu!ap), taiko, fruits, mania
- **数据库持久化**: MySQL 存储用户数据
- **缓存支持**: Redis 缓存令牌和会话信息
- **容器化部署**: Docker 和 Docker Compose 支持

## 快速开始

### 使用 Docker Compose (推荐)

1. 克隆项目
```bash
git clone https://github.com/GooGuTeam/osu_lazer_api.git
cd osu_lazer_api
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
| `PRIVATE_API_SECRET` | 私有 API 密钥，用于前后端 API 调用 | `your_private_api_secret_here` |

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
| `FETCHER_CALLBACK_URL` | Fetcher 回调 URL | `http://localhost:8000/fetcher/callback` |

### 日志设置
| 变量名 | 描述 | 默认值 |
|--------|------|--------|
| `LOG_LEVEL` | 日志级别 | `INFO` |

### 游戏设置
| 变量名 | 描述 | 默认值 |
|--------|------|--------|
| `ENABLE_OSU_RX` | 启用 osu!RX 统计数据 | `false` |
| `ENABLE_OSU_AP` | 启用 osu!AP 统计数据 | `false` |
| `ENABLE_ALL_MODS_PP` | 启用所有 Mod 的 PP 计算 | `false` |
| `ENABLE_SUPPORTER_FOR_ALL_USERS` | 启用所有新注册用户的支持者状态 | `false` |
| `ENABLE_ALL_BEATMAP_LEADERBOARD` | 启用所有谱面的排行榜 | `false` |
| `SEASONAL_BACKGROUNDS` | 季节背景图 URL 列表 | `[]` |

> **注意**: 在生产环境中，请务必更改默认的密钥和密码！

### 更新数据库

参考[数据库迁移指南](./MIGRATE_GUIDE.md)

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！
