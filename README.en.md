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

    Please see [wiki](https://github.com/GooGuTeam/g0v0-server/wiki/Configuration) to modify the .env file.
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

### Updating the Database

Refer to the [Database Migration Guide](https://github.com/GooGuTeam/g0v0-server/wiki/Migrate-Database)

## License

MIT License

## Contributing

The project is currently in a state of rapid iteration. Issues and Pull Requests are welcome!

See [Contributing Guide](./CONTRIBUTING.md) for more information.

## Discussion

- Discord: https://discord.gg/AhzJXXWYfF
- QQ Group: `1059561526`
