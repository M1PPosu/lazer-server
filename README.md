# osu! API 模拟服务器

这是一个使用 FastAPI + MySQL + Redis 实现的 osu! API 模拟服务器，提供了完整的用户认证和数据管理功能。

## 功能特性

- **OAuth 2.0 认证**: 支持密码流和刷新令牌流
- **用户数据管理**: 完整的用户信息、统计数据、成就等
- **多游戏模式支持**: osu!, taiko, fruits, mania
- **数据库持久化**: MySQL 存储用户数据
- **缓存支持**: Redis 缓存令牌和会话信息
- **容器化部署**: Docker 和 Docker Compose 支持

## API 端点

### 认证端点
- `POST /oauth/token` - OAuth 令牌获取/刷新

### 用户端点
- `GET /api/v2/me/{ruleset}` - 获取当前用户信息

### 其他端点
- `GET /` - 根端点
- `GET /health` - 健康检查

## 快速开始

### 使用 Docker Compose (推荐)

1. 克隆项目
```bash
git clone <repository-url>
cd osu_lazer_api
```

2. 启动服务
```bash
docker-compose up -d
```

3. 创建示例数据
```bash
docker-compose exec api python create_sample_data.py
```

4. 测试 API
```bash
# 获取访问令牌
curl -X POST http://localhost:8000/oauth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=password&username=Googujiang&password=password123&client_id=5&client_secret=FGc9GAtyHzeQDshWP5Ah7dega8hJACAJpQtw6OXk&scope=*"

# 使用令牌获取用户信息
curl -X GET http://localhost:8000/api/v2/me/osu \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### 本地开发

1. 安装依赖
```bash
pip install -r requirements.txt
```

2. 配置环境变量
```bash
# 复制服务器配置文件
cp .env .env.local

# 复制客户端配置文件（用于测试脚本）
cp .env.client .env.client.local
```

3. 启动 MySQL 和 Redis
```bash
# 使用 Docker
docker run -d --name mysql -e MYSQL_ROOT_PASSWORD=password -e MYSQL_DATABASE=osu_api -p 3306:3306 mysql:8.0
docker run -d --name redis -p 6379:6379 redis:7-alpine
```


4. 启动应用
```bash
uvicorn main:app --reload
```

## 项目结构

```
osu_lazer_api/
├── app/
│   ├── __init__.py
│   ├── models.py          # Pydantic 数据模型
│   ├── database.py        # SQLAlchemy 数据库模型
│   ├── config.py          # 配置设置
│   ├── dependencies.py    # 依赖注入
│   ├── auth.py           # 认证和令牌管理
│   └── utils.py          # 工具函数
├── main.py               # FastAPI 应用主文件
├── create_sample_data.py # 示例数据创建脚本
├── requirements.txt      # Python 依赖
├── .env                 # 环境变量配置
├── docker-compose.yml   # Docker Compose 配置
├── Dockerfile          # Docker 镜像配置
└── README.md           # 项目说明
```

## 示例用户

创建示例数据后，您可以使用以下凭据进行测试：

- **用户名**: `Googujiang`
- **密码**: `password123`
- **用户ID**: `15651670`

## 环境变量配置

项目包含两个环境配置文件：

### 服务器配置 (`.env`)
用于配置 FastAPI 服务器的运行参数：

| 变量名 | 描述 | 默认值 |
|--------|------|--------|
| `DATABASE_URL` | MySQL 数据库连接字符串 | `mysql+pymysql://root:password@localhost:3306/osu_api` |
| `REDIS_URL` | Redis 连接字符串 | `redis://localhost:6379/0` |
| `SECRET_KEY` | JWT 签名密钥 | `your-secret-key-here` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 访问令牌过期时间（分钟） | `1440` |
| `OSU_CLIENT_ID` | OAuth 客户端 ID | `5` |
| `OSU_CLIENT_SECRET` | OAuth 客户端密钥 | `FGc9GAtyHzeQDshWP5Ah7dega8hJACAJpQtw6OXk` |
| `HOST` | 服务器监听地址 | `0.0.0.0` |
| `PORT` | 服务器监听端口 | `8000` |
| `DEBUG` | 调试模式 | `True` |

### 客户端配置 (`.env.client`)
用于配置客户端脚本的 API 连接参数：

| 变量名 | 描述 | 默认值 |
|--------|------|--------|
| `OSU_CLIENT_ID` | OAuth 客户端 ID | `5` |
| `OSU_CLIENT_SECRET` | OAuth 客户端密钥 | `FGc9GAtyHzeQDshWP5Ah7dega8hJACAJpQtw6OXk` |
| `OSU_API_URL` | API 服务器地址 | `http://localhost:8000` |

> **注意**: 在生产环境中，请务必更改默认的密钥和密码！

## API 使用示例

### 获取访问令牌

```bash
curl -X POST http://localhost:8000/oauth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=password&username=Googujiang&password=password123&client_id=5&client_secret=FGc9GAtyHzeQDshWP5Ah7dega8hJACAJpQtw6OXk&scope=*"
```

响应：
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "Bearer",
  "expires_in": 86400,
  "refresh_token": "abc123...",
  "scope": "*"
}
```

### 获取用户信息

```bash
curl -X GET http://localhost:8000/api/v2/me/osu \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### 刷新令牌

```bash
curl -X POST http://localhost:8000/oauth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=refresh_token&refresh_token=YOUR_REFRESH_TOKEN&client_id=5&client_secret=FGc9GAtyHzeQDshWP5Ah7dega8hJACAJpQtw6OXk"
```

## 开发

### 添加新用户

您可以通过修改 `create_sample_data.py` 文件来添加更多示例用户，或者扩展 API 来支持用户注册功能。

### 扩展功能

- 添加更多 API 端点（排行榜、谱面信息等）
- 实现实时功能（WebSocket）
- 添加管理面板
- 实现数据导入/导出功能

### 迁移数据库

参考[数据库迁移指南](./MIGRATE_GUIDE.md)

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！
