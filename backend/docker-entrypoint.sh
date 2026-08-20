#!/bin/sh
# Backend container entry: migrate then start the app process.
# Alembic failures abort startup (no uvicorn). No seed scripts here.
set -eu

echo "docker-entrypoint: alembic upgrade head"
python -m alembic upgrade head

echo "docker-entrypoint: starting $*"
exec "$@"
