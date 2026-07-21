# Tutorial Aktor

Tutorial ini mengikuti empat peran utama aplikasi. Semua langkah mengacu pada fitur saat ini: autentikasi/scoped assignment, kurikulum, lifecycle RPS, CPMK-RPS/Sub-CPMK/indikator, 16 minggu, ujian paralel, eligibility UAS, blueprint asesmen, submission, rubrik/grading, rule/decision, integrity issue, attainment/trace, portfolio, Provus/CQI, PPEPP, feedback privat, dashboard, dan kemajuan pribadi.

## Mulai dalam satu perintah

1. Aktifkan Docker Desktop/Engine.
2. Buka terminal di root repositori dan jalankan `./scripts/quickstart.sh`.
3. Tunggu sampai muncul `OBE Apps siap` dan catat password demo.
4. Buka URL **Halaman login** yang dicetak (default <http://localhost:8000/accounts/login/>).
5. Pilih akun pada tabel di bawah. Semua akun memakai password demo yang sama.

Jika port 8000 sibuk, gunakan `./scripts/quickstart.sh --port 8080`. Jika output password sudah tertutup, buka `.env` dan lihat `OBE_DEMO_PASSWORD`. Data dan akun demo seluruhnya sintetis dan hanya tersedia pada profil local/test.

| Aktor | Username | Fokus utama | Tutorial |
|---|---|---|---|
| Prodi | `prodi` | approval RPS/kurikulum/formula/portfolio/report, rule/package, keputusan | [Tutorial Prodi](prodi.md) |
| GPM | `gpm` | review RPS/asesmen, trace, Provus/CQI, portfolio, PPEPP, feedback | [Tutorial GPM](gpm.md) |
| Pengampu | `pengampu` | RPS, instrumen/rubrik, nilai/evidence, attainment, portfolio/report | [Tutorial Pengampu](pengampu.md) |
| Mahasiswa | `mahasiswa` | submission/feedback, portfolio pribadi, keputusan dan banding | [Tutorial Mahasiswa](mahasiswa.md) |

Jika login menampilkan 403 CSRF, muat ulang halaman login dari URL yang dicetak quickstart. Untuk container dari versi lama, jalankan `./scripts/quickstart.sh --clean`. Perlindungan CSRF tetap harus aktif.

Fungsi DPA, koordinator, pembimbing, penguji, mentor, dan TPMF merupakan assignment terbatas, bukan akun utama. Assignment tersebut mengikuti scope objek, periode, aksi, dan expiry dari akun utama yang ditugaskan.
