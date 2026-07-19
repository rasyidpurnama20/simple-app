# Tutorial Prodi

## Tujuan

Prodi memantau kesehatan kurikulum, menilai temuan sebelum aktivasi, dan memberi approval tanpa melakukan self-approval.

## Masuk dan orientasi

1. Buka <http://localhost:8000/accounts/login/>.
2. Kelola akun melalui layanan Prodi, lalu berikan role dan assignment yang selalu dibatasi aksi, object, periode, serta expiry. Self-assignment tidak diperbolehkan.
3. Aktifkan fitur secara bertahap melalui flag `internal`/`pilot`/`general`; sertakan acceptance evidence dan rollback plan.
4. Masuk dengan username `prodi` dan password lokal yang ditampilkan oleh `setup-local.sh`.
5. Dashboard menampilkan agregat capaian CPL dari dataset sintetis v5. Status hijau menunjukkan snapshot tersedia, bukan persetujuan kurikulum.

## Tinjau kurikulum

1. Buka **Katalog** atau <http://localhost:8000/catalog/>.
2. Pastikan katalog memuat 77 mata kuliah, 66 outcome, dan 90 SKS pilihan tersedia.
3. Perhatikan status **Review** dan peringatan 129 SKS wajib. Gate aplikasi mensyaratkan tepat 126 SKS, sehingga data ini tidak boleh diaktifkan sebelum keputusan kurikulum dibuat.
4. Catat kode mata kuliah yang akan diubah melalui PR/perubahan data berikutnya; jangan mengoreksi fixture sumber secara diam-diam.

## Kelola aturan dan package cohort

1. Pastikan setiap cohort/tanggal hanya cocok dengan satu package: `LEGACY-ABCDE` untuk cohort 2020–2023 dan `CURRENT-AABBC` mulai 2024.
2. Buat perubahan sebagai versi rule/package `draft`; jangan mengedit versi `active`.
3. Minta GPM mereview schema input, expression, boundary, source version, dan dampak historis.
4. Aktifkan sebagai checker yang berbeda dari maker. Simpan alasan aktivasi dan golden replay pada acceptance evidence.
5. Bila ada keputusan gagal yang benar-benar memerlukan pengecualian, periksa reason, dokumen immutable, dampak, dan expiry; jangan mengubah data sumber untuk “meloloskan” keputusan.

## Hormati gate integritas

Publication, attainment, eligibility, kelulusan, laporan mutu, dan official sync harus dihentikan bila record memiliki blocking issue yang belum `verified`. Status `resolved` atau `accepted-risk` belum cukup untuk membuka gate.

## Kerjakan approval task

1. Buka **Tugas Saya**.
2. Cari tugas **Tinjau anomali 129 SKS wajib**.
3. Gunakan katalog dan dashboard sebagai bukti awal. Approval final tetap memerlukan pemisahan maker-checker dan bukti perubahan.

## Periksa Semantic Analytics

Buka <http://localhost:8000/api/v1/analytics/semantic/?metric=attainment>. Respons harus memuat 12 baris CPL, nilai aktual, target, denominator, coverage, dan formula version.

## Hasil yang diharapkan

- Prodi dapat menjelaskan mengapa kurikulum masih `review`.
- Tidak ada aktivasi ketika total SKS wajib belum memenuhi gate.
- Keputusan menggunakan agregat terverifikasi dan dapat ditelusuri ke dataset v5.
