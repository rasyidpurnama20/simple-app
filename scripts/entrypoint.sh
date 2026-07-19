#!/bin/sh
set -eu
python manage.py migrate --noinput
if [ "${OBE_ENV:-production}" = "local" ]; then
  python manage.py seed_demo
fi
exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 60 --access-logfile -
