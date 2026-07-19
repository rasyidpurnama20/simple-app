# OBE Apps

Platform OBE yang ringkas untuk menghubungkan **kurikulum → RPS → asesmen → bukti → capaian → CQI**. Aplikasi memakai Django + DRF, HTMX, Tailwind CSS, PostgreSQL, Valkey, RabbitMQ/Celery, dan Apache ECharts yang di-host lokal.

## Instalasi tercepat

Prasyarat: Docker dan Docker Compose.

```bash
./scripts/setup-local.sh
docker compose up --build
```

Buka <http://localhost:8000>. Data demo dibuat otomatis.

| Peran | Username |
|---|---|
| Prodi | `prodi` |
| GPM | `gpm` |
| Pengampu | `pengampu` |
| Mahasiswa | `mahasiswa` |

Password acak ditampilkan sekali oleh `setup-local.sh` dan tersimpan di `.env` privat. Seed demo otomatis ditolak saat mode production/non-debug.

Untuk menghentikan aplikasi:

```bash
docker compose down
```

Data tetap tersimpan di Docker volumes. Gunakan `docker compose down -v` hanya jika memang ingin menghapus seluruh data lokal.

## Perintah sehari-hari

```bash
# Lihat log
docker compose logs -f web worker

# Buat admin lokal
docker compose exec web python manage.py createsuperuser

# Jalankan test
docker compose exec web pytest

# Periksa migration
docker compose exec web python manage.py makemigrations --check --dry-run

# Masuk shell Django
docker compose exec web python manage.py shell
```

## Menjalankan tanpa Docker

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
./scripts/setup-local.sh
npm ci && npm run build
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

SQLite dipakai otomatis untuk pengembangan cepat; PostgreSQL tetap menjadi sumber kebenaran pada deployment Compose.

## Struktur singkat

```text
config/                     konfigurasi local/test/production/exam-edge
obe/
  shared/                   audit, outbox, feature flag, rules, file manifest
  identity/                 RBAC dan scoped assignment
  curriculum/               versi kurikulum, PL/CPL/BK/CPMK, 77 mata kuliah
  learning/                 offering, RPS, 16 minggu, kehadiran
  assessment/               instrumen, submission, nilai, attainment
  evidence/                 bukti immutable content-addressed
  analytics/                Semantic JSON + ECharts lokal
  quality/                  integrity issue, PPEPP, CQI
  ai/                       satu gateway LiteLLM dan AI kill switch
  secure_exam/              authoring, sesi, autosave, signed bundle
  academic_lifecycle/       status, IRS, hasil studi, task, notifikasi
  integration/              staging, validasi, rekonsiliasi
deploy/                     Nginx, Ansible, observability, SOPS, Exam Edge
docs/                       arsitektur, operasi, API, dan traceability PR-01–PR-88
tests/                      unit, contract, security, dan architecture tests
```

Impor model lintas domain dilarang. Modul berkomunikasi melalui `services`, `selectors`, command, atau domain event di transactional outbox. Jalankan `python tests/test_architecture.py` untuk memverifikasi batas ini.

## Quality gate

```bash
./scripts/check.sh
```

Gate mencakup Ruff, format, migration drift, unit/integration/contract tests, architecture test, dependency/secret scan, dan SBOM di CI. Baseline saat ini memiliki 41 test dan coverage 90%.

## Dokumentasi

- [Arsitektur](docs/ARCHITECTURE.md)
- [Kontrak API](docs/API.md)
- [Operasi, backup, dan restore](docs/OPERATIONS.md)
- [Keamanan](docs/SECURITY.md)
- [Traceability PR-01–PR-88](docs/TRACEABILITY.md)
- [Status implementasi dan release gate](docs/IMPLEMENTATION_STATUS.md)

## Catatan ruang lingkup

PR ini adalah baseline aplikasi yang runnable dan fondasi production-oriented. Sign-off UAT, benchmark kapasitas server/lab, hardening jaringan aktual, backup-restore rehearsal, dan go-live tujuh hari tetap harus dijalankan pada lingkungan institusi sebelum status production-ready diberikan.
