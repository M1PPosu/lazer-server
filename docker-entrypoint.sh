#!/bin/bash
set -e

echo "Waiting for database connection..."
while ! nc -z $MYSQL_HOST $MYSQL_PORT; do
  sleep 1
done
echo "Database connected"

echo "Running alembic..."
uv run --no-sync alembic upgrade head

exec "$@"
