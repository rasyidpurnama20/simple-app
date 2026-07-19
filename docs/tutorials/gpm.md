# Tutorial GPM

## Tujuan

GPM memverifikasi konsistensi data capaian, target, denominator, dan jejak formula sebelum memberi rekomendasi mutu.

## Masuk dan lihat capaian

1. Masuk di <http://localhost:8000/accounts/login/> dengan username `gpm`.
2. Pastikan assignment mutu masih aktif sebelum membuka analytics atau bukti lintas mata kuliah; akses yang dicabut langsung membatalkan sesi lama.
3. Pada dashboard, tunggu label **12 CPL terverifikasi**.
4. Buka tabel alternatif di bawah grafik radar dan bandingkan setiap nilai aktual dengan target 75.

## Verifikasi scope program dan mata kuliah

1. Buka endpoint program: <http://localhost:8000/api/v1/analytics/semantic/?metric=attainment>.
2. Pastikan `privacy_scope` bernilai `program-aggregate` dan setiap baris memiliki `formula_version`.
3. Uji satu mata kuliah melalui <http://localhost:8000/api/v1/analytics/semantic/?metric=attainment&course=MIK1624101>.
4. Cocokkan CPL yang muncul dengan pemetaan mata kuliah pada dataset. Jangan membandingkan nilai antar-scope tanpa melihat denominator.

## Kerjakan quality task

1. Buka **Tugas Saya**.
2. Pilih tugas **Verifikasi capaian CPL dataset v5**.
3. Jika ada actual kosong, coverage tidak masuk akal, atau formula version berubah tanpa migration note, kembalikan ke pemilik data.

## Review rule dan integrity issue

1. Pada rule `draft`, periksa required input, expression, priority, severity, cohort, dan effective period. Reviewer tidak boleh sama dengan maker.
2. Jalankan boundary, missing-input, conflict, serta replay test. Missing input harus menghasilkan `indeterminate`.
3. Untuk integrity issue, cocokkan reason code, source snapshot/checksum, evidence, owner, dan due date.
4. Setelah pemilik memperbaiki sumber, jalankan revalidation. Pindahkan `resolved` ke `verified` hanya bila finding tidak muncul lagi; update stale akan ditolak oleh lock version.
5. Saat mereview banding, gunakan evidence row dan source version dari decision snapshot. Pemohon tidak boleh menjadi reviewer.

## Review paket kurikulum

1. Jalankan laporan katalog, allocation, dan traceability pada versi `draft/review`.
2. Pastikan 5 PL, 12 CPL, 18 BK, 77 mata kuliah, dan 31 CPMK berasal dari versi sumber yang sama.
3. Tolak aktivasi bila total bobot parent meleset, mapping belum memiliki referensi approval, terdapat orphan/cycle, atau checksum paket berubah.
4. Untuk dataset demo, verifikasi blocker 129 SKS wajib serta CPMK22/CPMK27 tanpa inbound mapping. Finding tersebut adalah bukti validator bekerja, bukan alasan mengarang relasi.
5. Reviewer tidak boleh merangkap maker, approver, atau activator. Ikuti [runbook kurikulum](../CURRICULUM_RUNBOOK.md) untuk rehearsal dan rollback.

## Review RPS dan blueprint asesmen

1. Buka RPS berstatus `gpm_review`; cocokkan offering, semester, koordinator, dan curriculum version.
2. Periksa pemetaan CPMK-RPS→CPMK program/CPL, bobot CPMK-RPS/Sub-CPMK 100%, indikator observable, serta ketercakupan indikator oleh asesmen.
3. Periksa 16 minggu, UTS/UAS, metode dan waktu. Praktik harus terintegrasi, bukan membuat minggu ke-17.
4. Periksa blueprint instrumen: outcome, difficulty, form, waktu, coverage, evidence, dan total bobot 100%. Pastikan instrumen direncanakan published sebelum teaching starts.
5. Jika ada masalah, beri komentar pada field spesifik lalu **Kembalikan**. Jika valid, lanjutkan ke approval Prodi. Checksum akan mencegah approval stale ketika Pengampu mengubah payload sesudah review.
6. Selama semester, bandingkan planned-vs-actual. Deviasi harus memiliki alasan dan evidence; lakukan verifikasi sesuai assignment mutu.

## Moderasi ujian paralel

1. Buka question set pada parallel group yang sama dan pastikan jenis ujian, coverage, difficulty, serta checksum tersedia.
2. Bila soal berbeda, periksa alasan dan equivalence report. Tolak bila group kosong, blueprint tidak ekuivalen, atau bukti tidak cukup.
3. Selesaikan review GPM dan teruskan ke Prodi; reviewer GPM tidak boleh menjadi approver Prodi.
4. Setelah hasil tersedia, jalankan analisis disparity. Selisih di atas threshold menjadi temuan mutu untuk ditindaklanjuti, bukan alasan mengubah nilai otomatis.
5. Saat memeriksa eligibility UAS, gunakan snapshot held-only denominator, roster/IRS, reason code, source version, dan status override resmi.

## Hasil yang diharapkan

- GPM dapat membedakan agregat program dan mata kuliah.
- Temuan 129 SKS diperlakukan sebagai isu review, bukan dikoreksi otomatis.
- Data personal mahasiswa tidak digunakan pada laporan program.
- GPM dapat menunjukkan reason code dan field path setiap pengembalian RPS.
