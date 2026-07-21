#!/bin/sh
set -eu

echo "[Tahap 0] Menjalankan migration otomatis..."
python manage.py migrate --noinput

echo "[Tahap 0] Menyiapkan empat akun demo..."
python manage.py seed_stage0

echo "[Tahap 0] Tahap 0 siap. Buka http://localhost:${STAGE0_PORT:-8000}/accounts/login/"
exec "$@"
