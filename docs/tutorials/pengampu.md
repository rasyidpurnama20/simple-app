# Tutorial Pengampu

## Tujuan

Pengampu memakai katalog dan pemetaan capaian untuk menyiapkan RPS, asesmen, serta bukti yang konsisten pada mata kuliah yang ditugaskan.

## Masuk dan pilih mata kuliah

1. Masuk di <http://localhost:8000/accounts/login/> dengan username `pengampu`.
2. Akses RPS, asesmen, file, AI, dan background job mengikuti assignment mata kuliah/periode yang sama; URL object di luar scope akan ditolak.
3. Buka **Katalog** dan cari `MIK1624101` — Dasar Sistem.
4. Catat semester, SKS, dan jenis mata kuliah sebagai baseline penyusunan RPS.

## Periksa capaian mata kuliah

1. Buka <http://localhost:8000/api/v1/analytics/semantic/?metric=attainment&course=MIK1624101>.
2. Pastikan outcome yang muncul adalah CPL yang dipetakan ke mata kuliah tersebut.
3. Gunakan nilai aktual dan target hanya sebagai bukti agregat; nilai tersebut bukan pengganti rubrik atau nilai mahasiswa.

## Kerjakan tugas pengampu

1. Buka **Tugas Saya**.
2. Cari **Periksa pemetaan CPMK dan bukti asesmen**.
3. Sebelum menyatakan siap, pastikan CPMK, bobot asesmen, rubrik, dan evidence requirement konsisten. Workflow penerbitan tetap mengikuti draft Pengampu → review GPM → approval Prodi.

## Susun RPS dan 16 minggu

1. Pilih offering dan curriculum version yang aktif, lalu buat RPS `draft`. Jangan menyalin status `published-demo` fixture menjadi persetujuan resmi.
2. Isi referensi dan materi; buat CPMK-RPS yang terhubung ke CPMK program dan CPL.
3. Buat minimal satu Sub-CPMK per CPMK-RPS dan minimal satu indikator observable per Sub-CPMK. Total bobot CPMK-RPS dan setiap kelompok Sub-CPMK harus tepat 100%.
4. Isi minggu 1–16: UTS pada minggu 8, UAS pada minggu 16, serta outcome, indikator, topik, metode, aktivitas, tugas, dan tiga komponen waktu.
5. Jalankan validasi. Perbaiki seluruh reason code sebelum menekan **Ajukan review GPM**.
6. Jika RPS dikembalikan, buka komentar pada field yang ditunjuk, perbaiki draft, lalu ajukan ulang. Jangan mengedit RPS published; gunakan clone versi baru dengan alasan revisi.

## Siapkan asesmen, rubrik, dan nilai

1. Buat rubrik draft. Hubungkan setiap kriteria ke indikator dan Sub-CPMK; total bobot kriteria harus 100% dan rentang level tidak boleh overlap.
2. Buat butir saat instrumen masih draft. Kunci jawaban diberi klasifikasi `controlled` dan tidak tampil pada payload mahasiswa.
3. Buat enam/lebih instrumen sesuai kebutuhan. Lengkapi tujuan, peserta, jadwal, mode, attempt, assessor, evidence, mapping, dan blueprint; total rencana harus tepat 100%.
4. Publish rencana sebelum pengajaran. Setelah published atau dipakai untuk nilai, instrumen/rubrik/butir tidak dapat diedit.
5. Nilai melalui kriteria rubrik. Bila second marker diwajibkan, tunggu rekonsiliasi sebelum final. Regrade memakai rubrik versi baru dan alasan; nilai lama tetap tersimpan.
6. Setelah pertemuan, catat actual minutes, kehadiran, materi, dan evidence. Beri alasan bila ada deviasi dari rencana.

## Kelola ujian paralel dan eligibility UAS

1. Pastikan setiap kelas mempunyai offering, roster, IRS approved, jadwal, ruang, dosen, dan parallel group yang benar.
2. Buat question set UTS/UAS per kelas. Sistem mencatat checksum blueprint dan soal; soal berbeda wajib mempunyai alasan serta bukti coverage/difficulty ekuivalen.
3. Ajukan kepada GPM, lalu tunggu approval Prodi sebelum release. Jangan menyetujui question set yang Anda buat sendiri.
4. Rekam kehadiran per aktivitas. Aktivitas dibatalkan/pengecualian tidak menjadi denominator; periksa snapshot UAS yang menampilkan count, persen, reason code, dan source version.
5. Bila roster/IRS/kehadiran resmi bermasalah, koreksi sumber. Ajukan override hanya untuk pengecualian sah dengan alasan dan evidence; checker harus aktor berbeda.
6. Untuk nilai published yang salah, ajukan revisi beralasan. Approval menghasilkan score baru; score lama tidak diubah.

## Tindak lanjuti keputusan akademik

1. Buka explanation keputusan mata kuliah dan periksa rule code/version, field aktual, kondisi, evidence row, serta source version.
2. Jika input sumber keliru, koreksi melalui gradebook/kehadiran resmi lalu minta revalidation; decision snapshot lama tidak boleh diedit.
3. Jika pengecualian sah diperlukan, ajukan override dengan reason code, alasan, dokumen evidence immutable, dampak, dan expiry.
4. Pengampu sebagai maker tidak boleh menyetujui override sendiri. Effective outcome berubah menjadi `overridden` hanya setelah checker berwenang menyetujui.

## Hitung attainment dan susun laporan mutu

1. Buat formula draft dengan distribution instrumen/criterion/outcome tepat 100%; ajukan review GPM dan approval Prodi.
2. Publish score dan lengkapi evidence verified. Calculation fail-closed bila satu input belum resmi; jangan mengisi angka manual untuk menutup gap.
3. Recalculation selalu memakai snapshot sebelumnya dan alasan. Periksa diff actual, coverage, dan formula version sebelum memakai hasil baru.
4. Generate portfolio mata kuliah dari snapshot valid, evidence verified, finding, dan CQI. Regenerasi setelah perubahan data menghasilkan versi baru.
5. Buat draft report PPEPP semester dari RPS, asesmen, attendance, score, attainment, evidence, complaint, finding, CQI, dan effectiveness; lanjutkan ke GPM.
6. Tindak lanjuti feedback yang ditugaskan sampai actioned/closed dengan deadline dan closure evidence. Kasus restricted tidak boleh disalin ke dokumen umum.

## Hasil yang diharapkan

- Mata kuliah dan CPMK ditelusuri dari katalog yang sama.
- Data agregat tidak dipakai untuk menimpa nilai individual.
- Pengampu tidak dapat mereview atau menyetujui RPS miliknya sendiri.
- Setiap nilai dapat ditelusuri ke response, instrument, item/kriteria, rubrik version, outcome, assessor, dan audit.
