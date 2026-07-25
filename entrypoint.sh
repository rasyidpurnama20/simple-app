#!/usr/bin/env bash
# Startup entrypoint for the OBE System web container.
#
# Safe to re-run: waits for PostgreSQL, applies migrations (which also seed the
# demo Program of Study + demo users idempotently), then starts the server.
set -euo pipefail

DB_HOST="${POSTGRES_HOST:-db}"
DB_PORT="${POSTGRES_PORT:-5432}"
DB_USER="${POSTGRES_USER:-obe}"

echo "[entrypoint] Waiting for PostgreSQL at ${DB_HOST}:${DB_PORT} ..."
until pg_isready -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" >/dev/null 2>&1; do
    sleep 1
done
echo "[entrypoint] PostgreSQL is ready."

echo "[entrypoint] Applying database migrations ..."
python manage.py migrate --noinput

# Collect static files (safe no-op if none). Ignore failure in dev.
python manage.py collectstatic --noinput >/dev/null 2>&1 || true

echo "[entrypoint] Starting application: $*"
exec "$@"
