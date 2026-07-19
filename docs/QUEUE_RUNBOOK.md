# Runbook antrean dan worker

Valkey hanya menyimpan session, cache, rate limit, lock, hasil sementara, dan short-lived state. Data akademik tetap berasal dari PostgreSQL. RabbitMQ menjadi broker Celery dengan queue durable, batas panjang, TTL, overflow rejection, dan dead-letter exchange.

| Queue | Worker | Maksimum aktif | Fokus |
|---|---|---:|---|
| `interactive`, `academic-critical` | `worker-interactive` | 8 | pekerjaan singkat dan transaksi inti |
| `ai` | `worker-ai` | 2 | inferensi AI |
| `reports` | `worker-reports` | 2 | laporan dan analytics berat |
| `imports` | `worker-imports` | 1 | impor data |
| `notifications` | `worker-notifications` | 4 | notifikasi |
| `sync` | `worker-sync` | 2 | sinkronisasi dan Exam Edge |
| `batch`, `maintenance` | `worker-batch` | 2/1 | rekonsiliasi dan housekeeping |

Kebijakan lengkap berada di `obe/shared/queueing.py`. Setiap job dibuat dengan idempotency key, correlation ID, payload hash, expiry, progress, generation, dan lease. Cancellation menaikkan generation sehingga hasil worker lama dibuang. `reconcile_stale_work` mengembalikan lease kedaluwarsa ke status queued dan memulihkan outbox publisher yang berhenti.

## Rehearsal

1. Kirim job dengan idempotency key sama dua kali; side effect harus satu.
2. Hentikan RabbitMQ saat publish, hidupkan kembali, dan pastikan retry bounded.
3. Matikan worker ketika job berjalan; setelah lease habis job harus kembali queued.
4. Penuhi satu queue hingga `x-max-length`; publish berikutnya harus ditolak/dead-letter tanpa menjatuhkan web.
5. Batalkan job berjalan dan pastikan result generation lama tidak tersimpan.
6. Kirim poison message dan verifikasi metadata tanpa payload sensitif tersedia di `dead-letter`.

Jangan menaruh nilai mentah, jawaban ujian, file, atau prompt di payload. Simpan hanya identifier dan baca data kanonis dari PostgreSQL melalui permission service pada saat eksekusi.
