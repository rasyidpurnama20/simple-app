# PostgreSQL sebagai sumber kebenaran

- Deployment terkelola hanya menerima PostgreSQL. Koneksi memiliki health check, connect timeout, application name, dan `CONN_MAX_AGE` maksimum 600 detik.
- Objek revisable memakai UUID publik, version/effective period, actor create/update, dan `lock_version`. Semua update konkurensi menggunakan `update_versioned`; stale write ditolak.
- Foreign key domain memakai constraint database dan `PROTECT` pada data akademik/evidence yang tidak boleh menjadi orphan. Unique/check constraint didefinisikan di migration.
- Service write kritis berada dalam `transaction.atomic`. Deadlock/serialization failure hanya diulang terbatas oleh `run_with_deadlock_retry`.
- Query middleware menghitung budget setiap request. Query lambat hanya mencatat durasi dan fingerprint SHA-256, bukan SQL/parameter sensitif.
- Analytics, cache, export, AI output, dan event delivery adalah read/derived state. Regenerasi dataset demo/read model dilakukan dengan `python manage.py import_obe_sample --replace` dari sumber kanonik yang disetujui.

Sebelum promosi migration: jalankan `makemigrations --check`, pemeriksa reversibility, forward/backward pada salinan staging, integrity query untuk orphan, serta `EXPLAIN (ANALYZE, BUFFERS)` endpoint kritis. Target core read p95 adalah ≤2,5 detik dan query count tidak boleh melewati `OBE_QUERY_BUDGET`.
