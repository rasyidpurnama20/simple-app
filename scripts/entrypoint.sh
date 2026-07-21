#!/bin/sh
set -eu

run_init() {
  echo "[init] Menjalankan migrasi database otomatis..."
  python manage.py migrate --noinput
  if [ "${OBE_ENV:-production}" = "local" ]; then
    echo "[init] Menyinkronkan data dan akun demo lokal..."
    python manage.py seed_demo
  fi
  echo "[init] Database siap. 'No migrations to apply' berarti skema sudah terbaru."
}

case "${1:-web}" in
  init)
    run_init
    ;;
  web)
    echo "[web] Database sudah diinisialisasi; menjalankan Gunicorn..."
    exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 60 --access-logfile -
    ;;
  *)
    exec "$@"
    ;;
esac
