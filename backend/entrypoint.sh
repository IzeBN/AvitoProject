#!/bin/sh
set -e

echo "Running Alembic migrations..."
alembic upgrade head

# Если переданы аргументы — выполнить их (например ARQ worker)
if [ $# -gt 0 ]; then
    echo "Starting: $@"
    exec "$@"
fi

echo "Starting application..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
