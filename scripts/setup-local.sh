#!/bin/sh
set -eu
umask 077

generate_password() {
  od -An -N16 -tx1 /dev/urandom | tr -d ' \n'
}

if [ -e .env ] && [ ! -f .env ]; then
  echo "Gagal: .env ada tetapi bukan file biasa." >&2
  exit 1
fi

if [ ! -e .env ]; then
  if [ ! -f .env.example ]; then
    echo "Gagal: .env.example tidak ditemukan. Jalankan skrip dari root repositori." >&2
    exit 1
  fi
  cp .env.example .env
  status="dibuat"
else
  status="diperiksa"
fi

password="$(sed -n 's/^OBE_DEMO_PASSWORD=//p' .env | head -n 1)"
if [ "${#password}" -lt 16 ]; then
  password="$(generate_password)"
  temp_file=".env.tmp.$$"
  trap 'rm -f "$temp_file"' EXIT HUP INT TERM

  if grep -q '^OBE_DEMO_PASSWORD=' .env; then
    sed "s|^OBE_DEMO_PASSWORD=.*$|OBE_DEMO_PASSWORD=${password}|" .env > "$temp_file"
  else
    cp .env "$temp_file"
    printf '\nOBE_DEMO_PASSWORD=%s\n' "$password" >> "$temp_file"
  fi

  mv "$temp_file" .env
  trap - EXIT HUP INT TERM
  status="diperbaiki"
fi

chmod 600 .env
echo "Setup lokal siap; .env ${status}. Password demo: ${password}"
