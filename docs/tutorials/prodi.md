# Tutorial Prodi

## Tujuan

Prodi memantau kesehatan kurikulum, menilai temuan sebelum aktivasi, dan memberi approval tanpa melakukan self-approval.

## Masuk dan orientasi

1. Buka <http://localhost:8000/accounts/login/>.
2. Masuk dengan username `prodi` dan password lokal yang ditampilkan oleh `setup-local.sh`.
3. Dashboard menampilkan agregat capaian CPL dari dataset sintetis v5. Status hijau menunjukkan snapshot tersedia, bukan persetujuan kurikulum.

## Tinjau kurikulum

1. Buka **Katalog** atau <http://localhost:8000/catalog/>.
2. Pastikan katalog memuat 77 mata kuliah, 66 outcome, dan 90 SKS pilihan tersedia.
3. Perhatikan status **Review** dan peringatan 129 SKS wajib. Gate aplikasi mensyaratkan tepat 126 SKS, sehingga data ini tidak boleh diaktifkan sebelum keputusan kurikulum dibuat.
4. Catat kode mata kuliah yang akan diubah melalui PR/perubahan data berikutnya; jangan mengoreksi fixture sumber secara diam-diam.

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
