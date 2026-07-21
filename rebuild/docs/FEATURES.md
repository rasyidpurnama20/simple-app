# Katalog Fitur Tahap 0

Dokumen ini mencatat tujuan dan cara memakai setiap fitur yang benar-benar tersedia.
Daftar ini juga mencegah fitur lama dianggap sudah menjadi bagian rebuild.

## F-01 — Startup dua container

**Tujuan:** memberi satu jalur instalasi yang dapat dijelaskan tanpa antrean, cache,
proxy, atau service persiapan terpisah.

**Aktor:** pengguna lokal atau pengembang.

**Tutorial:** jalankan `docker compose -f rebuild/docker-compose.yml up --build`, lalu
tunggu `web` dan `db` berstatus sehat.

**Hasil:** tepat dua container berjalan. PostgreSQL tidak membuka port ke host dan web
hanya terikat pada loopback komputer lokal.

## F-02 — Migration otomatis

**Tujuan:** menyiapkan schema tanpa perintah manual dan tanpa container `init`.

**Aktor:** otomatis oleh `web` sebelum Gunicorn dimulai.

**Tutorial:** lihat log awal `web`. Baris migration muncul sebelum `Tahap 0 siap`.

**Hasil:** migration yang belum ada diterapkan; pesan `No migrations to apply` berarti
schema sudah terbaru dan bukan error.

## F-03 — Seed akun demo idempotent

**Tujuan:** selalu menyediakan empat akun uji yang konsisten tanpa menggandakan user.

**Aktor:** otomatis oleh `web` setelah migration.

**Tutorial:** login dengan `prodi`, `gpm`, `pengampu`, dan `mahasiswa`. Restart `web`,
lalu login lagi.

**Hasil:** tetap empat akun, masing-masing tepat satu group/peran. Password mengikuti
`STAGE0_DEMO_PASSWORD` bila variabel itu diberikan.

## F-04 — Login dan proteksi dashboard

**Tujuan:** membuktikan sesi autentikasi serta mencegah pengguna anonim masuk dashboard.

**Aktor:** seluruh peran.

**Tutorial:** buka `/dashboard/` tanpa login; aplikasi mengarahkan ke login. Masuk memakai
akun demo dan pastikan dashboard terbuka.

**Hasil:** autentikasi berhasil dan akses anonim ditolak.

## F-05 — Dashboard identitas peran

**Tujuan:** menyepakati arti peran sebelum memberi kewenangan akademik.

**Aktor:** Prodi, GPM, Pengampu, dan Mahasiswa.

**Tutorial:** masuk bergantian dengan empat akun dan cocokkan isi dashboard dengan
[definisi peran](ROLES.md).

**Hasil:** satu akun hanya melihat tujuan perannya; fitur yang ditunda ditandai jelas.

## F-06 — Logout

**Tujuan:** mengakhiri sesi dengan tindakan eksplisit yang dilindungi CSRF.

**Aktor:** seluruh pengguna terautentikasi.

**Tutorial:** klik **Keluar** di dashboard.

**Hasil:** sesi berakhir dan halaman kembali ke login.

## F-07 — Health check

**Tujuan:** membuat Docker dan pengguna dapat membedakan aplikasi sehat dari proses yang
sekadar hidup.

**Aktor:** Docker Compose, CI, dan pengembang.

**Tutorial:** buka <http://localhost:8000/healthz/> atau lihat kolom health pada `docker compose ps`.

**Hasil:** endpoint merespons `{"status":"ok","stage":0}`.

## F-08 — Penyimpanan saat restart

**Tujuan:** memastikan restart aplikasi tidak sama dengan reset database.

**Aktor:** pengguna lokal.

**Tutorial:** jalankan `docker compose -f rebuild/docker-compose.yml restart web`, tunggu
sehat, lalu login kembali.

**Hasil:** akun tetap ada karena database disimpan pada volume
`obe-stage0-postgres-data`.
