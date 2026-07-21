# OBE Apps

Platform OBE yang ringkas untuk menghubungkan **kurikulum → RPS → asesmen → bukti → capaian → CQI**. Aplikasi memakai Django + DRF, HTMX, Tailwind CSS, PostgreSQL, Valkey, RabbitMQ/Celery, dan Apache ECharts yang di-host lokal.

Sumber kebutuhan normatif adalah `Spesifikasi_Utama_Pengembangan_OBE_Apps_PR-01-PR-88.md` dengan SHA-256 `f404527ecfd3b81000e8fcb640a469147c60d0308ef2930fdbe3811eae610be2`. Kebutuhan di luar dokumen tersebut wajib diajukan melalui PR baru. Bukti implementasi per requirement dicatat di [traceability](docs/TRACEABILITY.md).

## Instalasi tercepat

Prasyarat: Docker Desktop atau Docker Engine yang sedang aktif.

```bash
./scripts/quickstart.sh
```

Satu perintah tersebut memeriksa Docker, menyiapkan `.env`, membangun satu image aplikasi bersama beserta image Nginx, lalu menjalankan service `init`. Service ini menerapkan migration dan menyinkronkan seed demo sebelum web/worker/beat boleh hidup. Entrypoint Linux dinormalisasi di dalam image sehingga checkout Windows/CRLF tidak memerlukan perbaikan manual. Setelah pesan `OBE Apps siap` muncul, buka halaman login yang dicetak oleh quickstart (default: <http://localhost:8000/accounts/login/>).

Pesan Django `No migrations to apply` adalah **sukses**, bukan error: database sudah menggunakan migration terbaru. Tidak perlu menjalankan `python manage.py migrate` secara manual.

Gunakan quickstart sebagai satu-satunya jalur instalasi lokal; tidak perlu menjalankan `docker compose up` atau memasang Nginx secara manual. Setelah menarik perbaikan terbaru, cukup jalankan:

```bash
git pull
./scripts/quickstart.sh --clean
```

| Peran | Username | Mulai menggunakan aplikasi |
|---|---|---|
| Prodi | `prodi` | [Tutorial Prodi](docs/tutorials/prodi.md) |
| GPM | `gpm` | [Tutorial GPM](docs/tutorials/gpm.md) |
| Pengampu | `pengampu` | [Tutorial Pengampu](docs/tutorials/pengampu.md) |
| Mahasiswa | `mahasiswa` | [Tutorial Mahasiswa](docs/tutorials/mahasiswa.md) |

Keempat akun memakai password demo yang sama. Password acak ditampilkan oleh quickstart dan tersimpan sebagai `OBE_DEMO_PASSWORD` di `.env` privat. Setiap quickstart menyinkronkan password akun dengan nilai tersebut, jadi kredensial yang dicetak selalu dapat digunakan. Akun dan data ini sintetis; seed demo otomatis ditolak saat mode production/non-debug.

Data demo memakai normalisasi aman `sample-data-2020-2026-obe-spec-v5`: 5 PL, 12 CPL, 18 bahan kajian, 31 CPMK, 77 mata kuliah, 2 package cohort, 11 academic rule, serta irisan RPS/asesmen `MIK1624101` (1 CPMK-RPS, 3 Sub-CPMK, 3 indikator, 16 minggu, 6 instrumen, dan 2 rubrik). Detail provenance tersedia di [panduan dataset v5](docs/DATASET_V5.md).

Jika percobaan sebelumnya gagal, ulangi dari container bersih tanpa menghapus data:

```bash
./scripts/quickstart.sh --clean
```

Jika port `8000` sudah dipakai, jalankan `./scripts/quickstart.sh --port 8080` lalu buka <http://localhost:8080>.

Jika browser pernah membuka halaman login sebelum stack terbaru siap, muat ulang halaman login lalu coba kembali. Origin CSRF `localhost`/`127.0.0.1` untuk port quickstart dikonfigurasi otomatis; tidak perlu menonaktifkan perlindungan CSRF.

Panduan error umum, stop/start, dan reset total tersedia di [panduan instalasi lokal](docs/LOCAL_SETUP.md).

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

# Impor ulang dataset v5 secara idempotent
docker compose exec web python manage.py import_obe_sample

# Impor file v5 penuh dan simpan bukti rekonsiliasi
docker compose exec web python manage.py import_obe_sample \
  --path /data/sample-data-2020-2026-obe-spec-v5.json \
  --report /app/var/import-reconciliation-v5.json
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

## Lingkungan dan secret

Profil `local`, `test`, `staging`, `production`, dan `exam-edge` terpisah serta divalidasi saat startup. Deployment terkelola menggunakan SOPS dan file runtime `*_FILE`; plaintext secret tidak disimpan di repositori.

- Mulai dari template di [`deploy/env`](deploy/env/).
- Ikuti [runbook secret dan rotasi](docs/SECRETS_RUNBOOK.md).
- Audit pemenuhan PR-04 tersedia di [penerimaan PR-04](docs/PR04_ACCEPTANCE.md).

Deployment production memakai compose terpisah dengan image digest immutable dan Ansible. Lihat [runbook deployment](docs/DEPLOYMENT_RUNBOOK.md); operasi sehari-hari tersedia melalui `python -m scripts.obe_ops`.

Pekerjaan asinkron memakai antrean bounded dan worker terisolasi; perubahan domain diteruskan melalui outbox/inbox idempoten dan ditelusuri menggunakan correlation ID. Lihat [runbook antrean](docs/QUEUE_RUNBOOK.md), [domain event](docs/EVENTS_RUNBOOK.md), dan [observability](docs/OBSERVABILITY_RUNBOOK.md).

Keamanan berlapis memakai rate limit per endpoint/aktor, scoped permission tunggal, account lock/MFA opsional, audit hash-chain append-only, serta feature flag dan kill switch berversi. Keputusan akademik memakai rule/package immutable, snapshot replay, override terpisah, dan gate integritas data; lihat [runbook aturan akademik](docs/ACADEMIC_RULES_RUNBOOK.md) dan [runbook integritas data](docs/DATA_INTEGRITY_RUNBOOK.md).

Kurikulum memakai lifecycle maker-reviewer-approver-activator, paket JSON/CSV ber-checksum, clone/diff/rollback, serta weighted trace PL→CPL→BK→mata kuliah→CPMK. Lihat [runbook kurikulum](docs/CURRICULUM_RUNBOOK.md) dan [penerimaan PR-19–PR-24](docs/PR19_PR24_ACCEPTANCE.md). Dataset demo sengaja tetap `review` karena 129 SKS wajib dan CPMK22/CPMK27 belum memiliki mapping sumber.

RPS dan asesmen memakai checksum approval yang replayable, komentar per field, desain 16 minggu, blueprint 100%, rubrik/butir berversi, controlled answer key, second marker, dan regrade tanpa menimpa nilai lama. Mulai dari [runbook RPS dan asesmen](docs/RPS_ASSESSMENT_RUNBOOK.md) serta [penerimaan PR-25–PR-29](docs/PR25_PR29_ACCEPTANCE.md).

Siklus hasil OBE memakai formula attainment berversi dan fail-closed, trace maju/balik, portfolio reproducible, evaluasi Provus/CQI, laporan PPEPP empat aktor, serta feedback anonim/restricted. Ikuti [runbook quality loop](docs/QUALITY_LOOP_RUNBOOK.md) dan [penerimaan PR-34–PR-39](docs/PR34_PR39_ACCEPTANCE.md).

## Tutorial berdasarkan aktor

| Aktor | Fitur utama | Panduan |
|---|---|---|
| Prodi | approval RPS, versi rule/package, aktivasi maker-checker | [Tutorial Prodi](docs/tutorials/prodi.md) |
| GPM | review RPS per field, validasi blueprint dan realisasi | [Tutorial GPM](docs/tutorials/gpm.md) |
| Pengampu | susun RPS/16 minggu, instrumen, rubrik, grading | [Tutorial Pengampu](docs/tutorials/pengampu.md) |
| Mahasiswa | instrumen, submission, feedback, keputusan pribadi | [Tutorial Mahasiswa](docs/tutorials/mahasiswa.md) |

Fungsi DPA, koordinator, pembimbing, penguji, mentor, dan TPMF dijalankan sebagai assignment terbatas dari peran utama. Lihat [indeks tutorial aktor](docs/tutorials/README.md) untuk batas scope-nya.

## Struktur singkat

```text
config/                     konfigurasi local/test/staging/production/exam-edge
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

Dependency graph kanonik bersifat searah:

```mermaid
flowchart TD
  C[Curriculum] --> L[Learning]
  L --> A[Assessment]
  A --> E[Evidence dan Attainment]
  E --> Q[Quality dan CQI]
  Q --> C
```

Siklus pada gambar adalah siklus proses bisnis, bukan dependency impor Python. Semua domain hanya boleh bergantung pada shared kernel atau kontrak `service`, `selector`, `command`, dan domain event. Architecture test membangun graph impor aktual dan menggagalkan circular dependency, direct cross-domain model access, serta akses AI di luar `obe.ai.gateway`.

Perubahan schema/API wajib mengikuti aturan berikut:

- Migration harus deterministik; `RunPython` dan `RunSQL` wajib memiliki operasi balik atau forward-fix plan yang disetujui.
- API publik dan event contract harus versioned, backward-compatible selama masa transisi, serta memiliki contract test.
- Perubahan breaking memakai endpoint/event version baru, migration plan, dampak data, feature flag, dan rollback pada deskripsi PR.
- Modul baru dimulai dari [template modul](docs/module-template/README.md) agar URL, permission, service, API, migration, test, audit, dan feature flag tersedia sejak awal.

## Quality gate

```bash
./scripts/check.sh
```

Gate mencakup Ruff, format, migration drift, unit/integration/contract tests, architecture test, dependency/secret scan, dan SBOM di CI. Baseline saat ini memiliki 148 test dengan coverage minimum 85% dan gate tambahan per domain kritis, termasuk curriculum, learning/assessment, evidence, identity, dan shared decision engine. Acceptance file v5 penuh mengimpor seluruh mahasiswa tanpa `--student-limit`, lalu mengulang import untuk membuktikan idempotensi.

## Dokumentasi

- [Arsitektur](docs/ARCHITECTURE.md)
- [Kontrak API](docs/API.md)
- [Operasi, backup, dan restore](docs/OPERATIONS.md)
- [Keamanan](docs/SECURITY.md)
- [Baseline keamanan aplikasi dan jaringan](docs/SECURITY_RUNBOOK.md)
- [Identity, RBAC, dan scoped assignment](docs/IDENTITY_RUNBOOK.md)
- [Audit append-only dan signed export](docs/AUDIT_RUNBOOK.md)
- [Feature flag dan kill switch](docs/FEATURE_FLAG_RUNBOOK.md)
- [Aturan, package cohort, decision, override, dan banding](docs/ACADEMIC_RULES_RUNBOOK.md)
- [Validasi dan gate integritas data akademik](docs/DATA_INTEGRITY_RUNBOOK.md)
- [Lifecycle, paket, dan traceability kurikulum](docs/CURRICULUM_RUNBOOK.md)
- [Lingkungan, SOPS, rotasi, dan revokasi secret](docs/SECRETS_RUNBOOK.md)
- [Deployment reproducible](docs/DEPLOYMENT_RUNBOOK.md)
- [PostgreSQL dan concurrency](docs/DATABASE_RUNBOOK.md)
- [Evidence immutable](docs/EVIDENCE_RUNBOOK.md)
- [Valkey, RabbitMQ, dan worker Celery](docs/QUEUE_RUNBOOK.md)
- [Transactional outbox dan domain event](docs/EVENTS_RUNBOOK.md)
- [OpenTelemetry, dashboard, SLO, dan alert](docs/OBSERVABILITY_RUNBOOK.md)
- [Traceability PR-01–PR-88](docs/TRACEABILITY.md)
- [Status implementasi dan release gate](docs/IMPLEMENTATION_STATUS.md)
- [Tata kelola CI dan branch](docs/CI_GOVERNANCE.md)
- [Audit penerimaan PR-01–PR-03](docs/PR01_PR03_ACCEPTANCE.md)
- [Audit penerimaan PR-04](docs/PR04_ACCEPTANCE.md)
- [Audit penerimaan PR-05–PR-07](docs/PR05_PR07_ACCEPTANCE.md)
- [Audit penerimaan PR-08–PR-10](docs/PR08_PR10_ACCEPTANCE.md)
- [Audit penerimaan PR-11–PR-14](docs/PR11_PR14_ACCEPTANCE.md)
- [Audit penerimaan PR-15–PR-18](docs/PR15_PR18_ACCEPTANCE.md)
- [Audit penerimaan PR-19–PR-24](docs/PR19_PR24_ACCEPTANCE.md)
- [Runbook RPS dan asesmen](docs/RPS_ASSESSMENT_RUNBOOK.md)
- [Audit penerimaan PR-25–PR-29](docs/PR25_PR29_ACCEPTANCE.md)
- [Runbook attainment, portfolio, CQI, PPEPP, dan feedback](docs/QUALITY_LOOP_RUNBOOK.md)
- [Audit penerimaan PR-34–PR-39](docs/PR34_PR39_ACCEPTANCE.md)
- [Dataset sintetis v5](docs/DATASET_V5.md)
- [Tutorial seluruh aktor](docs/tutorials/README.md)

## Catatan ruang lingkup

PR ini adalah baseline aplikasi yang runnable dan fondasi production-oriented. Sign-off UAT, benchmark kapasitas server/lab, hardening jaringan aktual, backup-restore rehearsal, dan go-live tujuh hari tetap harus dijalankan pada lingkungan institusi sebelum status production-ready diberikan.
