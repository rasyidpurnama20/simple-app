#!/bin/sh
set -eu

usage() {
  cat <<'EOF'
Penggunaan: ./scripts/quickstart.sh [--clean] [--port PORT]

Menyiapkan konfigurasi, membangun image, dan menjalankan OBE Apps.
  --clean  hentikan container lama sebelum mulai; volume/data tetap dipertahankan
  --port   gunakan port host lain, misalnya --port 8080
EOF
}

clean=0
requested_port=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --clean)
      clean=1
      shift
      ;;
    --port)
      if [ "$#" -lt 2 ]; then
        echo "Gagal: --port memerlukan nomor port." >&2
        usage >&2
        exit 2
      fi
      requested_port="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage >&2
      exit 2
      ;;
  esac
done

validate_port() {
  case "$1" in
    ""|*[!0-9]*)
      echo "Gagal: port harus berupa angka 1-65535." >&2
      exit 2
      ;;
  esac
  if [ "$1" -lt 1 ] || [ "$1" -gt 65535 ]; then
    echo "Gagal: port harus berada pada rentang 1-65535." >&2
    exit 2
  fi
}

if [ -n "$requested_port" ]; then
  validate_port "$requested_port"
fi

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
root_dir="$(CDPATH= cd -- "$script_dir/.." && pwd)"
cd "$root_dir"

if ! command -v docker >/dev/null 2>&1; then
  echo "Gagal: Docker belum terpasang atau tidak tersedia di PATH." >&2
  echo "Pasang Docker Desktop/Engine, lalu jalankan kembali perintah ini." >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Gagal: Docker tidak aktif atau akun Anda belum dapat mengakses daemon Docker." >&2
  echo "Jalankan Docker Desktop/daemon, lalu coba kembali." >&2
  exit 1
fi

if docker compose version >/dev/null 2>&1; then
  compose() {
    docker compose "$@"
  }
  compose_label="docker compose"
elif command -v docker-compose >/dev/null 2>&1 && docker-compose version >/dev/null 2>&1; then
  compose() {
    docker-compose "$@"
  }
  compose_label="docker-compose"
else
  echo "Gagal: Docker Compose tidak ditemukan." >&2
  echo "Aktifkan plugin Compose atau pasang Docker Desktop versi terbaru." >&2
  exit 1
fi

"$root_dir/scripts/setup-local.sh"

if [ -n "$requested_port" ]; then
  http_port="$requested_port"
elif [ -n "${OBE_HTTP_PORT:-}" ]; then
  http_port="$OBE_HTTP_PORT"
else
  http_port="$(sed -n 's/^OBE_HTTP_PORT=//p' .env | head -n 1)"
  http_port="${http_port:-8000}"
fi
validate_port "$http_port"
export OBE_HTTP_PORT="$http_port"

if [ "$clean" -eq 1 ]; then
  echo "Membersihkan container lama (volume/data tetap aman)..."
  compose down --remove-orphans
fi

echo "Membangun dan menjalankan OBE Apps di background..."
if ! compose up --build --detach --remove-orphans; then
  echo "Gagal menjalankan container. Ringkasan log:" >&2
  compose logs --tail=100 web db valkey rabbitmq nginx >&2 || true
  echo "Jika port ${http_port} sedang dipakai, coba: ./scripts/quickstart.sh --port 8080" >&2
  exit 1
fi

if ! compose exec -T nginx nginx -t >/dev/null 2>&1; then
  echo "Nginx gagal memuat konfigurasi. Status dan log terakhir:" >&2
  compose ps >&2 || true
  compose logs --tail=100 nginx >&2 || true
  exit 1
fi

echo "Menunggu aplikasi siap (maksimal 3 menit)..."
attempt=0
while [ "$attempt" -lt 90 ]; do
  if compose exec -T nginx wget -q --spider http://127.0.0.1/healthz/ >/dev/null 2>&1; then
    password="$(sed -n 's/^OBE_DEMO_PASSWORD=//p' .env | head -n 1)"
    cat <<EOF

OBE Apps siap: http://localhost:${http_port}
Username      : prodi / gpm / pengampu / mahasiswa
Password      : ${password}

Perintah bantuan:
  ${compose_label} logs -f web       # lihat log
  ${compose_label} down              # berhenti, data tetap aman
  ./scripts/quickstart.sh --clean    # ulangi dari container bersih
EOF
    exit 0
  fi
  attempt=$((attempt + 1))
  sleep 2
done

echo "Aplikasi belum siap setelah 3 menit. Status dan log terakhir:" >&2
compose ps >&2 || true
compose logs --tail=100 web db valkey rabbitmq nginx >&2 || true
echo "Setelah memperbaiki pesan di atas, coba: ./scripts/quickstart.sh --clean" >&2
exit 1
