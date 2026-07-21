# Tutorial Prodi

## Tujuan

Prodi memantau kesehatan kurikulum, menilai temuan sebelum aktivasi, dan memberi approval tanpa melakukan self-approval.

## Instalasi dan login

1. Aktifkan Docker Desktop/Engine, lalu dari root repositori jalankan `./scripts/quickstart.sh`.
2. Tunggu pesan `OBE Apps siap`. Buka URL **Halaman login** yang dicetak; default-nya <http://localhost:8000/accounts/login/>.
3. Masuk dengan username `prodi` dan password demo yang dicetak. Jika terlewat, buka `.env` dan lihat `OBE_DEMO_PASSWORD`.
4. Jika muncul 403 CSRF, muat ulang halaman login. Untuk stack lama, jalankan `./scripts/quickstart.sh --clean` lalu buka kembali URL login.
5. Dashboard menampilkan agregat capaian CPL dari dataset sintetis v5. Status hijau menunjukkan snapshot tersedia, bukan persetujuan kurikulum.

## Lima menit pertama

1. Buka **Katalog** dan konfirmasi dataset memuat 77 mata kuliah.
2. Buka **Tugas Saya**, lalu cari **Tinjau anomali 129 SKS wajib**.
3. Kembali ke dashboard dan periksa ringkasan 12 CPL sebelum mengikuti alur detail di bawah.

Untuk penggunaan non-demo, kelola akun melalui layanan Prodi dan berikan role/assignment yang dibatasi aksi, object, periode, serta expiry. Self-assignment tidak diperbolehkan. Aktifkan fitur bertahap melalui flag `internal`/`pilot`/`general` disertai acceptance evidence dan rollback plan.

## Tinjau kurikulum

1. Buka **Katalog** atau <http://localhost:8000/catalog/>.
2. Pastikan katalog memuat 77 mata kuliah, 66 outcome, dan 90 SKS pilihan tersedia.
3. Perhatikan status **Review** dan peringatan 129 SKS wajib. Gate aplikasi mensyaratkan tepat 126 SKS, sehingga data ini tidak boleh diaktifkan sebelum keputusan kurikulum dibuat.
4. Periksa finding traceability: dataset saat ini tidak memetakan CPMK22 dan CPMK27. Jangan membuat relasi otomatis tanpa dasar keputusan akademik.
5. Catat kode mata kuliah yang akan diubah melalui versi/clone berikutnya; jangan mengoreksi fixture sumber secara diam-diam.

## Kelola versi dan mapping kurikulum

1. Impor atau clone paket sebagai `draft`, lalu bandingkan perubahan PL/CPL/BK/mata kuliah/CPMK melalui diff.
2. Periksa setiap kelompok bobot PL→CPL, CPL→BK, BK→mata kuliah, mata kuliah→CPMK, dan CPL→CPMK. Total parent harus 100±0,01.
3. Bobot `derived-proportional` adalah usulan sistem. Berikan `approval_reference` hanya setelah dasar akademiknya diverifikasi; equal-split otomatis ditolak.
4. Ajukan review, lampirkan dokumen pengesahan, lalu gunakan aktor berbeda untuk maker, reviewer, approver, dan activator.
5. Setelah aktif, versi beserta outcome, mata kuliah, dan mapping menjadi immutable. Perubahan berikutnya dilakukan melalui clone; rollback hanya ke arsip ber-checksum valid.

Contoh teknis dan prosedur recovery tersedia di [runbook kurikulum](../CURRICULUM_RUNBOOK.md).

## Kelola aturan dan package cohort

1. Pastikan setiap cohort/tanggal hanya cocok dengan satu package: `LEGACY-ABCDE` untuk cohort 2020–2023 dan `CURRENT-AABBC` mulai 2024.
2. Buat perubahan sebagai versi rule/package `draft`; jangan mengedit versi `active`.
3. Minta GPM mereview schema input, expression, boundary, source version, dan dampak historis.
4. Aktifkan sebagai checker yang berbeda dari maker. Simpan alasan aktivasi dan golden replay pada acceptance evidence.
5. Bila ada keputusan gagal yang benar-benar memerlukan pengecualian, periksa reason, dokumen immutable, dampak, dan expiry; jangan mengubah data sumber untuk “meloloskan” keputusan.

## Hormati gate integritas

Publication, attainment, eligibility, kelulusan, laporan mutu, dan official sync harus dihentikan bila record memiliki blocking issue yang belum `verified`. Status `resolved` atau `accepted-risk` belum cukup untuk membuka gate.

## Setujui dan publikasikan RPS

1. Buka RPS berstatus `prodi_approval`; pastikan review GPM tersedia dan aktornya berbeda dari Pengampu/Prodi approver.
2. Periksa snapshot validasi: field wajib, mapping outcome, 16 minggu, blueprint, evidence, total asesmen 100%, dan seluruh komentar blocking sudah ditangani.
3. Setujui hanya jika checksum payload sama dengan checksum review. Bila payload berubah, sistem menolak stale approval dan RPS harus direview ulang.
4. Publish versi yang disetujui. Snapshot lengkap dan checksum disimpan untuk replay; versi tersebut immutable.
5. Perubahan kebijakan/perkuliahan berikutnya dimulai dari clone versi baru dengan alasan revisi. Rollback dilakukan sebagai versi baru, bukan mengubah snapshot lama.
6. Gunakan laporan rubrik dan second-marker untuk memantau konsistensi grading; regrade wajib menyimpan rubrik baru, alasan, nilai lama, dan audit.

## Setujui ujian paralel dan koreksi nilai

1. Pastikan GPM sudah mereview minimal dua question set dalam parallel group serta menyatakan coverage/difficulty ekuivalen.
2. Periksa kebijakan aktif. Jika `strict_same_question` aktif, soal berbeda harus diblokir; bila tidak aktif, alasan perbedaan tetap wajib.
3. Setujui sebagai aktor yang berbeda dari reviewer. Question set baru dapat dirilis setelah approval ini.
4. Pantau disparity pascaujian dan minta tindak lanjut mutu bila melewati threshold; jangan menyamakan nilai kelas secara otomatis.
5. Pada perubahan score published, pastikan reason dan recalculation tersedia. Maker tidak boleh menjadi checker; approval membuat versi score baru serta notifikasi, sedangkan nilai lama tetap auditable.

## Kerjakan approval task

1. Buka **Tugas Saya**.
2. Cari tugas **Tinjau anomali 129 SKS wajib**.
3. Gunakan katalog dan dashboard sebagai bukti awal. Approval final tetap memerlukan pemisahan maker-checker dan bukti perubahan.

## Setujui formula, portfolio, dan laporan PPEPP

1. Aktifkan formula attainment hanya setelah dibuat Pengampu dan direview GPM; ketiga aktor harus berbeda dan distribution wajib tepat 100%.
2. Tolak snapshot yang memiliki blocking reason, evidence belum verified, score belum published, denominator/mapping hilang, atau path tidak cocok.
3. Setujui portfolio hanya bila `incomplete_sections` kosong. Publish tidak mengubah package checksum; perubahan data membuat versi pengganti.
4. Setujui laporan PPEPP sesudah review GPM dan sebelum review scoped TPMF. Report published memerlukan empat aktor berbeda dan seluruh bagian semester lengkap.
5. Pantau CQI `ineffective/reopened` dan accepted risk. Accepted risk harus mempunyai alasan; ia tidak otomatis memverifikasi integrity blocker.

## Periksa Semantic Analytics

Buka <http://localhost:8000/api/v1/analytics/semantic/?metric=attainment>. Respons harus memuat 12 baris CPL, nilai aktual, target, denominator, coverage, dan formula version.

## Hasil yang diharapkan

- Prodi dapat menjelaskan mengapa kurikulum masih `review`.
- Tidak ada aktivasi ketika total SKS wajib belum memenuhi gate.
- Keputusan menggunakan agregat terverifikasi dan dapat ditelusuri ke dataset v5.
- RPS official published selalu memiliki reviewer, approver, snapshot replayable, dan checksum yang sama.
