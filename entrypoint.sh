#!/usr/bin/env bash
set -e

export FLASK_APP=run.py

echo "[entrypoint] ensuring instance directories..."
mkdir -p instance/storage/car_images instance/storage/excel_uploads instance/storage/chroma

# kindsisters → wecarcar1 DB 파일명 마이그레이션 (기존 데이터 보존)
if [ -f instance/kindsisters_auto.db ] && [ ! -f instance/wecarcar1_auto.db ]; then
  echo "[entrypoint] renaming kindsisters_auto.db -> wecarcar1_auto.db"
  mv instance/kindsisters_auto.db instance/wecarcar1_auto.db
fi

echo "[entrypoint] applying database migrations..."
flask db upgrade

echo "[entrypoint] seeding admin account..."
flask seed-admin

echo "[entrypoint] starting gunicorn on :5000..."
exec gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 180 "run:app"
