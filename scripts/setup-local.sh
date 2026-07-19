#!/bin/sh
set -eu
umask 077

if [ -e .env ]; then
  echo ".env sudah ada; tidak diubah."
  exit 0
fi

password="$(dd if=/dev/urandom bs=18 count=1 2>/dev/null | base64 | tr -d '\n')"
sed "s|^OBE_DEMO_PASSWORD=.*$|OBE_DEMO_PASSWORD=${password}|" .env.example > .env
echo "Setup lokal siap. Password demo: ${password}"
