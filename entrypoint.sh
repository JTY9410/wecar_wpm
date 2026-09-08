#!/usr/bin/env bash
set -e

export FLASK_APP=run.py

APP_UID="${APP_UID:-10001}"
APP_GID="${APP_GID:-10001}"

# Fix bind-mounted SQLite volume ownership, then drop to non-root (agent.md).
_drop_privileges() {
  if [ "$(id -u)" = "0" ]; then
    mkdir -p instance/storage/car_images instance/storage/excel_uploads instance/storage/chroma
    chown -R "${APP_UID}:${APP_GID}" instance || true
    exec gosu "${APP_UID}:${APP_GID}" "$@"
  fi
  exec "$@"
}

# Allow docker-compose `command:` overrides (e.g. dedicated scheduler process).
if [ "$#" -gt 0 ]; then
  _drop_privileges "$@"
fi

echo "[entrypoint] ensuring instance directories..."
mkdir -p instance/storage/car_images instance/storage/excel_uploads instance/storage/chroma

# kindsisters → wecarcar1 DB 파일명 마이그레이션 (기존 데이터 보존)
if [ -f instance/kindsisters_auto.db ] && [ ! -f instance/wecarcar1_auto.db ]; then
  echo "[entrypoint] renaming kindsisters_auto.db -> wecarcar1_auto.db"
  mv instance/kindsisters_auto.db instance/wecarcar1_auto.db
fi

if [ "$(id -u)" = "0" ]; then
  echo "[entrypoint] fixing instance volume ownership for uid ${APP_UID}..."
  chown -R "${APP_UID}:${APP_GID}" instance || true
  echo "[entrypoint] dropping privileges to appuser..."
  exec gosu "${APP_UID}:${APP_GID}" "$0"
fi

echo "[entrypoint] applying database migrations..."
flask db upgrade

echo "[entrypoint] seeding admin account..."
flask seed-admin

echo "[entrypoint] starting gunicorn on :5000 (non-root)..."
exec gunicorn --bind 0.0.0.0:5000 \
  --worker-class gthread --workers 2 --threads 4 \
  --timeout 300 --graceful-timeout 30 --keep-alive 5 \
  --access-logfile - --error-logfile - \
  "wsgi:app"
