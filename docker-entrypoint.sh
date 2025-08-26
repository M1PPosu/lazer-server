#!/usr/bin/env sh
set -eu

MYSQL_HOST="${MYSQL_HOST:-localhost}"
MYSQL_PORT="${MYSQL_PORT:-3306}"

echo "Waiting for database connection at ${MYSQL_HOST}:${MYSQL_PORT} ..."
# -w 2 加个超时，避免卡死
until nc -z -w 2 "$MYSQL_HOST" "$MYSQL_PORT"; do
  sleep 1
done
echo "Database connected."

echo "Running alembic..."
uv run --no-sync alembic upgrade head

# 把控制权交给最终命令
exec "$@"
