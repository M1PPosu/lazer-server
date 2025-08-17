# g0v0-server

[简体中文](./README.md) | English

This is an osu! API server implemented with FastAPI + MySQL + Redis, supporting most features of osu! API v1, v2, and osu!lazer.

## Features

-   **OAuth 2.0 Authentication**: Supports password and refresh token flows.
-   **User Data Management**: Complete user information, statistics, achievements, etc.
-   **Multi-game Mode Support**: osu! (RX, AP), taiko (RX), catch (RX), mania.
-   **Database Persistence**: MySQL for storing user data.
-   **Cache Support**: Redis for caching tokens and session information.
-   **Multiple Storage Backends**: Supports local storage, Cloudflare R2, and AWS S3.
-   **Containerized Deployment**: Docker and Docker Compose support.

## Quick Start

### Using Docker Compose (Recommended)

1.  Clone the project
    ```bash
    git clone https://github.com/GooGuTeam/g0v0-server.git
    cd g0v0-server
    ```
2.  Create a `.env` file

    Please see the server configuration below to modify the .env file.
    ```bash
    cp .env.example .env
    ```
3.  Start the service
    ```bash
    # Standard server
    docker-compose -f docker-compose.yml up -d
    # Enable osu!RX and osu!AP statistics (ppy-sb pp algorithm)
    docker-compose -f docker-compose-osurx.yml up -d
    ```
4.  Connect to the server from the game

    Use a [custom osu!lazer client](https://github.com/GooGuTeam/osu), or use [LazerAuthlibInjection](https://github.com/MingxuanGame/LazerAuthlibInjection), and change the server settings to the server's address.

## Configuration

### Database Settings
| Variable Name | Description | Default Value |
|---|---|---|
| `MYSQL_HOST` | MySQL host address | `localhost` |
| `MYSQL_PORT` | MySQL port | `3306` |
| `MYSQL_DATABASE` | MySQL database name | `osu_api` |
| `MYSQL_USER` | MySQL username | `osu_api` |
| `MYSQL_PASSWORD` | MySQL password | `password` |
| `MYSQL_ROOT_PASSWORD` | MySQL root password | `password` |
| `REDIS_URL` | Redis connection string | `redis://127.0.0.1:6379/0` |

### JWT Settings
| Variable Name | Description | Default Value |
|---|---|---|
| `JWT_SECRET_KEY` | JWT signing key | `your_jwt_secret_here` |
| `ALGORITHM` | JWT algorithm | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token expiration time (minutes) | `1440` |

### Server Settings
| Variable Name | Description | Default Value |
|---|---|---|
| `HOST` | Server listening address | `0.0.0.0` |
| `PORT` | Server listening port | `8000` |
| `DEBUG` | Debug mode | `false` |
| `SERVER_URL` | Server URL | `http://localhost:8000` |
| `CORS_URLS` | Additional CORS allowed domain list (JSON format) | `[]` |
| `FRONTEND_URL` | Frontend URL, redirects to this URL when accessing URLs opened from the game. Empty means no redirection. | `(null)` |

### OAuth Settings
| Variable Name | Description | Default Value |
|---|---|---|
| `OSU_CLIENT_ID` | OAuth client ID | `5` |
| `OSU_CLIENT_SECRET` | OAuth client secret | `FGc9GAtyHzeQDshWP5Ah7dega8hJACAJpQtw6OXk` |
| `OSU_WEB_CLIENT_ID` | Web OAuth client ID | `6` |
| `OSU_WEB_CLIENT_SECRET` | Web OAuth client secret | `your_osu_web_client_secret_here` |

### SignalR Server Settings
| Variable Name | Description | Default Value |
|---|---|---|
| `SIGNALR_NEGOTIATE_TIMEOUT` | SignalR negotiation timeout (seconds) | `30` |
| `SIGNALR_PING_INTERVAL` | SignalR ping interval (seconds) | `15` |

### Fetcher Settings

The Fetcher is used to get data from the official osu! API using OAuth 2.0 authentication.

| Variable Name | Description | Default Value |
|---|---|---|
| `FETCHER_CLIENT_ID` | Fetcher client ID | `""` |
| `FETCHER_CLIENT_SECRET` | Fetcher client secret | `""` |
| `FETCHER_SCOPES` | Fetcher scopes | `public` |

### Log Settings
| Variable Name | Description | Default Value |
|---|---|---|
| `LOG_LEVEL` | Log level | `INFO` |

### Sentry Settings
| Variable Name | Description | Default Value |
|---|---|---|
| `SENTRY_DSN` | Sentry DSN, empty to disable Sentry | `(null)` |

### Game Settings
| Variable Name | Description | Default Value |
|---|---|---|
| `ENABLE_RX` | Enable RX mod statistics | `false` |
| `ENABLE_AP` | Enable AP mod statistics | `false` |
| `ENABLE_ALL_MODS_PP` | Enable PP calculation for all mods | `false` |
| `ENABLE_SUPPORTER_FOR_ALL_USERS` | Enable supporter status for all new users | `false` |
| `ENABLE_ALL_BEATMAP_LEADERBOARD` | Enable leaderboards for all beatmaps | `false` |
| `ENABLE_ALL_BEATMAP_PP` | Allow any beatmap to grant PP | `false` |
| `SUSPICIOUS_SCORE_CHECK` | Enable suspicious score check (star>25 & acc<80 or pp>2300) | `true` |
| `SEASONAL_BACKGROUNDS` | List of seasonal background URLs | `[]` |

### Storage Service Settings

Used for storing replay files, avatars, and other static assets.

| Variable Name | Description | Default Value |
|---|---|---|
| `STORAGE_SERVICE` | Storage service type: `local`, `r2`, `s3` | `local` |
| `STORAGE_SETTINGS` | Storage service configuration (JSON format), see below for configuration | `{"local_storage_path": "./storage"}` |

## Storage Service Configuration

### Local Storage (Recommended for development)

Local storage saves files to the server's local filesystem, suitable for development and small-scale deployments.

```bash
STORAGE_SERVICE="local"
STORAGE_SETTINGS='{"local_storage_path": "./storage"}'
```

### Cloudflare R2 Storage (Recommended for production)

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

### AWS S3 Storage

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

> **Note**: In a production environment, be sure to change the default keys and passwords!

### Updating the Database

Refer to the [Database Migration Guide](https://github.com/GooGuTeam/g0v0-server/wiki/Migrate-Database)

## License

MIT License

## Contributing

The project is currently in a state of rapid iteration. Issues and Pull Requests are welcome!

## Discussion

- Discord: https://discord.gg/AhzJXXWYfF
- QQ Group: `1059561526`
