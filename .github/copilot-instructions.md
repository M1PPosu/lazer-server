## g0v0-server – AI Coding Agent Quick Guide

Focus: High‑performance osu! (v1 / v2 / lazer) API emulator. Python (FastAPI + SQLModel/MySQL + Redis + APScheduler) + Rust (`packages/msgpack_lazer_api` for MessagePack encode/decode).

### Core Architecture (know these before editing)
1. Entry: `main.py` – FastAPI app + lifespan startup/shutdown orchestration (fetcher init, GeoIP, schedulers, cache/email/download health checks, Redis message system, stats, achievements). Add new long‑running startup logic here only if it is foundational; otherwise prefer a scheduler or on‑demand service.
2. Routers (`app/router/`):
    - `v1/` & `v2/`: Must mirror official endpoints only (no custom additions). Keep prefix via parent `router = APIRouter(prefix="/api/v2")` etc.
    - `notification/`: Chat & notification subset (also “official only”).
    - `auth.py`: Auth / token flows.
    - `private/`: Server‑specific or internal endpoints (place all custom APIs here; split by concern with small modules + include via `private/router.py`).
3. Services (`app/service/`): Stateless or stateful domain logic (pp calc, rankings, caching, daily challenge, email, geoip, etc.). If you need background computation, create a service + (optionally) scheduler wrapper.
4. Schedulers (`app/scheduler/`): Start/stop functions named `start_*_scheduler` + matching `stop_*`. Lifespan wires them; stay consistent (see `cache_scheduler`, `database_cleanup_scheduler`).
5. Database layer (`app/database/`): SQLModel models; large models (e.g. `score.py`) embed domain helpers & serialization validators. When adding/altering tables: generate Alembic migration (autogenerate) & review for types / indexes.
6. Caching: Redis accessed via dependency (`app/dependencies/database.get_redis`). High‑traffic objects (users, user scores) use `UserCacheService` with explicit key patterns (`user:{id}...`). Reuse existing service; do not invent new ad‑hoc keys for similar data.
7. Rust module: `packages/msgpack_lazer_api` – performance critical (MessagePack for lazer). After Rust edits: `maturin develop -R` (release) inside dev container; Python interface consumed via import `msgpack_lazer_api` (see usage in encode/decode paths – keep function signatures stable; update `.pyi` if API changes).

### Common Task Playbooks
Add v2 endpoint: create file under `app/router/v2/`, import router via `from .router import router`, define FastAPI path ops (async) using DB session (`session: Database`) & caching patterns; avoid blocking calls. Do NOT modify existing prefixes; do NOT add non‑official endpoints here (place in `private`).
Add background job: put pure logic in `app/service/<name>_job.py` (idempotent / retry‑safe), add small scheduler starter in `app/scheduler/<name>_scheduler.py` exposing `start_<name>_scheduler()` & `stop_<name>_scheduler()`, then register in `main.lifespan` near similar tasks.
DB schema change: edit / add SQLModel in relevant module, then: `alembic revision --autogenerate -m "feat(db): add <table>"` → inspect migration (indexes, enums) → `alembic upgrade head`.
pp / ranking recalculation: standalone scriptable path via env `RECALCULATE=true python main.py` (see `app/service/recalculate.py`). Keep heavy loops async + batched (`asyncio.gather`) like `_recalculate_pp` pattern.
User data responses: Use `UserResp.from_db(...)` and cache asynchronously (`background_task.add_task(cache_service.cache_user, user_resp)`). Maintain ≤50 result limits where existing code does (see `v2/user.py`).

### Configuration & Safety
Central settings: `app/config.py` (pydantic-settings). Secrets default to unsafe placeholders; lifespan logs warnings if not overridden (`secret_key`, `osu_web_client_secret`). When introducing new config flags: add field + defaults, document in README tables, and reference via `settings.<name>` (avoid reading env directly elsewhere).

### Conventions / Quality
Commit messages: Angular format (type(scope): subject). Types: feat/fix/docs/style/refactor/perf/test/chore/ci.
Async only in request paths (no blocking I/O). Use existing redis/service helpers instead of inline logic. Prefer model methods / helper functions near existing ones for cohesion.
Cache keys: follow established prefixes (`user:` / `v1_user:` / `user:{id}:scores:`). Invalidate via provided service methods.
Error handling: Raise `HTTPException` for client issues; wrap external fetch retries (see `_recalculate_pp` loop with capped retries + sleep). Avoid silent except; log via `logger`.

### Tooling / Commands
Setup: `uv sync` → `pre-commit install`.
Run dev server: `uvicorn main:app --reload --host 0.0.0.0 --port 8000` (logs managed by custom logger; uvicorn default log config disabled).
Rust rebuild: `maturin develop -R`.
Migrations: `alembic revision --autogenerate -m "feat(db): ..."` → `alembic upgrade head`.

### When Modifying Large Files (e.g. `score.py`)
Keep validation / serializer patterns (field_validator / field_serializer). Add new enum-like JSON fields with both validator + serializer for forward compatibility.

### PR Scope Guidance
One concern per change (e.g., add endpoint OR refactor cache logic—not both). Update README config tables if adding env vars.

Questions / ambiguous patterns: prefer aligning with closest existing service; if still unclear, surface a clarification comment instead of introducing a new pattern.

— End of instructions —
