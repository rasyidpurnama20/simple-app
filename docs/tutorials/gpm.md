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

## Hasil yang diharapkan

- GPM dapat membedakan agregat program dan mata kuliah.
- Temuan 129 SKS diperlakukan sebagai isu review, bukan dikoreksi otomatis.
- Data personal mahasiswa tidak digunakan pada laporan program.
