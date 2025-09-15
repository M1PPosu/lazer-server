# GitHub Copilot Instructions for g0v0-server

This is an osu! API simulation server built with FastAPI, supporting osu! API v1/v2 and osu!lazer client functionality.

## Architecture Overview

**Entry Point:** `main.py` orchestrates startup/shutdown with complex lifespan management including fetchers, GeoIP, schedulers, cache systems, Redis messaging, and achievement loading.

**Router Organization:**
- `app/router/v1/` - osu! API v1 endpoints (must match [official v1 spec](https://github.com/ppy/osu-api/wiki))
- `app/router/v2/` - osu! API v2 endpoints (must match [official v2 OpenAPI spec](https://osu.ppy.sh/docs/openapi.yaml))
- `app/router/private/` - Custom/internal endpoints not in official APIs
- `app/router/auth.py` - OAuth 2.0 authentication flows
- `app/router/notification/` - Chat and notification systems

**Data Layer:**
- SQLModel ORM with async MySQL (`app/models/`, `app/database/`)
- Redis for caching, sessions, and messaging (`app/service/*_cache_service.py`)
- Alembic migrations in `migrations/`

**Background Systems:**
- `app/scheduler/` - Background job schedulers (cache refresh, cleanup, rankings)
- `app/service/` - Business logic services (user ranking, email queue, asset proxy)
- Native Rust module `packages/msgpack_lazer_api/` for fast MessagePack serialization

## Development Workflows

**Environment Setup:**
```bash
uv sync                           # Install dependencies
pre-commit install               # Setup git hooks
maturin develop -R               # Build native Rust module (when changed)
```

**Database Operations:**
```bash
alembic revision --autogenerate -m "feat(db): description"  # Create migration
alembic upgrade head                                        # Apply migrations
```

**Development Server:**
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Code Quality:**
```bash
pre-commit run --all-files       # Run all checks
pyright                         # Type checking
ruff .                          # Linting and formatting
```

## Key Patterns & Conventions

**Route Handlers:**
- Always async with dependency injection for DB/Redis
- Keep handlers thin - business logic goes in `app/service/`
- Use `UserCacheService` for user data caching patterns
- Background tasks for async cache updates: `bg_tasks.add_task()`

**Database Access:**
```python
# Inject database session
async def endpoint(session: AsyncSession = Depends(get_session)):
    # Use select() with specific columns for performance
    stmt = select(User.id, User.username).where(User.active == True)
    # Use exists() for existence checks
    exists_stmt = select(exists().where(User.id == user_id))
```

**Caching Patterns:**
```python
# Redis key naming: "user:{id}:profile", "beatmap:{id}:data"
# Use UserCacheService.get_user_resp() for cached user responses
# MessagePack serialization via native module for compact storage
```

**Error Handling:**
- `HTTPException` for client errors with proper status codes
- Structured logging with loguru for server-side issues
- Sentry integration for production error tracking

**Authentication:**
- OAuth 2.0 with multiple flows (password, authorization_code, client_credentials)
- v1 API uses API key in query parameter `k`
- JWT tokens with configurable expiration

## Critical Integration Points

**Asset Proxy System:** Routes osu! asset URLs (avatars, beatmap covers) through custom domain - see `app/service/asset_proxy_*.py`

**Game Mode Support:** Multi-mode with RX/AP variants - mode handling in `app/models/score.py`

**Rate Limiting:** FastAPI-limiter with Redis backend - different limits for download vs general APIs

**Native Module:** Rust MessagePack encoder/decoder in `packages/msgpack_lazer_api/` - rebuild with `maturin develop -R` after changes

**Background Schedulers:** Multiple concurrent schedulers for rankings, cache warming, database cleanup - managed in lifespan handlers

## API Compliance Rules

- **v1/v2 endpoints MUST match official osu! API specifications exactly**
- Custom endpoints go in `app/router/private/` only
- Maintain response schema compatibility - breaking changes require migration plan
- Use existing `*Resp` models for consistent response formats

## Configuration

Environment-driven via Pydantic Settings in `app/config.py`:
- Database: MySQL with async aiomysql driver
- Cache: Redis for sessions, rate limiting, messaging
- Storage: Local, S3, or Cloudflare R2 backends
- Optional: Sentry, New Relic, email SMTP

See project wiki for complete `.env` configuration guide.