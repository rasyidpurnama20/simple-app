# Peta OBE Apps Rebuild v1

Rebuild v1 memakai checkpoint pengguna. Satu tahap hanya boleh menghasilkan alur kecil
yang dapat dicoba dalam 10–15 menit. Tahap berikutnya tidak dimulai hanya karena test
otomatis hijau; persetujuan pengguna tetap wajib.

| Tahap | Pertanyaan yang harus dijawab | Status |
|---|---|---|
| 0 | Apakah instalasi, login, empat peran, dan restart mudah serta stabil? | Sedang dibangun |
| 1 | Apakah Prodi dapat menyusun kurikulum draft minimum dengan jelas? | Ditunda |
| 2 | Apakah Pengampu dapat membuat RPS dan satu asesmen sederhana? | Ditunda |
| 3 | Apakah nilai dua mahasiswa menghasilkan CPMK/CPL yang dapat dijelaskan? | Ditunda |
| 4 | Apakah GPM dan Prodi dapat menutup satu siklus review mutu/CQI? | Ditunda |

## Aturan pengembangan

1. Aplikasi lama tetap ada sebagai referensi; Tahap 0 berada di folder `rebuild/`.
2. Data contoh 54 MB tidak dipakai dan tidak dijalankan ketika container mulai.
3. Setiap fitur memiliki tujuan, aktor, tutorial, hasil yang diharapkan, dan test.
4. Satu PR berisi satu checkpoint yang dapat diamati pengguna.
5. Status CI hijau diperlukan, tetapi tidak menggantikan uji pengguna.
6. Tahap berikutnya hanya dimulai setelah kalimat **“Tahap ini sudah benar.”**

## Navigasi Tahap 0

- [Ruang lingkup dan kriteria penerimaan](STAGE_0.md)
- [Definisi empat peran](ROLES.md)
- [Katalog fitur beserta tujuan dan tutorial](FEATURES.md)
- [Checklist uji pengguna](USER_TEST.md)
- [Operasi dan pemecahan masalah](TROUBLESHOOTING.md)
