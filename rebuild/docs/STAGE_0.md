# Tahap 0 — Instalasi dan Login

## Tujuan

Membuktikan fondasi teknis dan konsep peran dengan bentuk terkecil yang bisa dicoba.
Tahap ini dinyatakan berhasil bila pengguna memahami apa yang berjalan, dapat masuk
sebagai empat peran, dan dapat memulai ulang aplikasi tanpa kehilangan data.

## Ruang lingkup

- Django melayani halaman login, dashboard peran, logout, dan health check.
- PostgreSQL menyimpan user, group/peran, session, dan migration.
- Migration serta seed empat akun dijalankan otomatis oleh container `web`.
- Hanya dua container: `web` dan `db`.
- Satu volume bernama menyimpan database pada restart biasa.

## Sengaja belum ada

- Kurikulum, CPL, mata kuliah, CPMK, RPS, asesmen, nilai, capaian, CQI, atau laporan.
- Nginx, Valkey, RabbitMQ, Celery worker/beat, service init, AI, dan observability.
- Impor dataset penuh maupun data mahasiswa nyata.
- Deployment production. Tahap 0 hanya boleh dibuka di komputer lokal.

## Kriteria penerimaan

| ID | Bukti yang harus terlihat |
|---|---|
| T0-01 | Satu perintah membangun dan memulai aplikasi. |
| T0-02 | `docker compose ... ps` hanya memperlihatkan `web` dan `db`. |
| T0-03 | Kedua container sehat tanpa langkah migration manual. |
| T0-04 | Empat akun demo dapat login dan melihat identitas peran yang tepat. |
| T0-05 | Pengguna anonim tidak dapat membuka dashboard. |
| T0-06 | Logout bekerja melalui tombol di dashboard. |
| T0-07 | Restart `web` tidak menghapus akun atau data PostgreSQL. |
| T0-08 | Halaman menjelaskan fitur yang tersedia dan yang masih ditunda. |
| T0-09 | Test otomatis, kontrak dua container, dan health check lulus di CI. |
| T0-10 | Pengguna menyelesaikan checklist dan menyatakan “Tahap 0 sudah benar.” |

Tidak ada migration manual, seed manual, atau penghapusan volume dalam alur normal.
