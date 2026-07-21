# Tutorial Mahasiswa

## Tujuan

Mahasiswa melihat tugas dan riwayat akademiknya sendiri tanpa memperoleh akses ke data mahasiswa lain.

## Instalasi dan login

1. Aktifkan Docker Desktop/Engine, lalu dari root repositori jalankan `./scripts/quickstart.sh`.
2. Tunggu pesan `OBE Apps siap`. Buka URL **Halaman login** yang dicetak; default-nya <http://localhost:8000/accounts/login/>.
3. Masuk dengan username `mahasiswa` dan password demo yang dicetak. Jika terlewat, buka `.env` dan lihat `OBE_DEMO_PASSWORD`.
4. Jika muncul 403 CSRF, muat ulang halaman login. Untuk stack lama, jalankan `./scripts/quickstart.sh --clean` lalu buka kembali URL login.
5. Akun demo dipetakan ke identitas mahasiswa sintetis; tidak ada data mahasiswa produksi.

## Lima menit pertama

1. Buka **Kemajuan** dan cocokkan NIM sintetis, SKS lulus, serta IPK.
2. Buka **Tugas Saya**, lalu cari **Periksa riwayat studi dan capaian pribadi**.
3. Kembali ke halaman Kemajuan untuk mencocokkan tugas dengan daftar hasil studi.

Pada penggunaan non-demo, gunakan reset kredensial bila diperlukan dan selesaikan MFA jika akun mengaktifkannya. Sistem menolak ID mahasiswa lain walaupun URL diubah manual.

## Lihat kemajuan pribadi

1. Buka **Kemajuan** atau <http://localhost:8000/me/progress/>.
2. Periksa NIM sintetis, SKS lulus, IPK terhitung, dan daftar hasil studi.
3. Nilai dihitung dari record yang diimpor. Bila mata kuliah atau hasil tidak dikenal, laporkan kepada Pengampu/Prodi dan jangan mengubah data sumber sendiri.

## Kerjakan tugas

1. Buka **Tugas Saya**.
2. Cari **Periksa riwayat studi dan capaian pribadi**.
3. Cocokkan hasil dengan halaman Kemajuan. Gunakan kanal akademik resmi bila memerlukan koreksi.

## Ikuti asesmen dan baca feedback

1. Buka instrumen yang tersedia untuk offering sendiri. Periksa tujuan, jadwal, mode, attempt limit, bobot, dan evidence yang wajib diunggah.
2. Kirim response dan evidence sebelum batas waktu; simpan receipt/checksum submission. Kunci jawaban dan data peserta lain tidak tersedia pada payload mahasiswa.
3. Setelah nilai published, baca skor, feedback per kriteria, rubrik version, dan status moderasi. Blind reference tidak mengungkap identitas marker.
4. Bila terjadi regrade, sistem menampilkan nilai terbaru dengan jejak versi; nilai dan alasan sebelumnya tetap tersimpan untuk audit.
5. Ajukan koreksi melalui kanal resmi bila response/evidence yang ditampilkan tidak sesuai receipt. Jangan membuat submission ganda di luar attempt yang diizinkan.

Submission dapat disimpan sebagai draft dan diganti pada attempt yang sama. Setelah **Final**, response menjadi immutable dan receipt SHA-256 menjadi bukti penerimaan. Reopening hanya dapat dilakukan petugas melalui aksi resmi beralasan. Submission lewat deadline hanya diterima bila kebijakan late mengizinkan dan tetap ditandai `late`.

Sebelum UAS, periksa eligibility yang menampilkan jumlah aktivitas hadir, denominator aktivitas terlaksana, persentase, dan reason code. Batas standar adalah 75%; aktivitas dibatalkan tidak menurunkan persentase. Bila IRS, roster, atau kehadiran resmi tidak sesuai, ajukan koreksi sumber melalui kanal akademik.

## Pahami keputusan dan ajukan banding

1. Pada keputusan blocking milik sendiri, baca rule code/version, input yang digunakan, kondisi gagal, sumber data, dan langkah perbaikan. Mahasiswa tidak dapat membuka decision mahasiswa lain.
2. Laporkan koreksi sumber kepada Pengampu/Prodi; decision snapshot historis tidak dihapus atau ditimpa.
3. Bila keputusan tetap diperselisihkan, ajukan banding sebelum expiry dengan pernyataan dan dokumen bukti.
4. Pantau state `submitted`, `information-needed`, `reviewed`, lalu `approved`/`rejected` dan `closed`. Lengkapi informasi ketika diminta; pemohon tidak dapat mereview bandingnya sendiri.

## Lihat konteks program

Dashboard dan katalog bersifat agregat/program. Mahasiswa boleh melihatnya sebagai konteks, tetapi tidak boleh menyimpulkan posisi mahasiswa lain dari agregat tersebut.

## Lihat portfolio dan kirim masukan

1. Portfolio pribadi hanya menampilkan capaian dan evidence milik sendiri; ubah URL mahasiswa lain harus menghasilkan akses ditolak.
2. Periksa denominator, coverage, formula/source version, status verifikasi, dan bagian yang belum lengkap sebelum memakai portfolio sebagai dokumen resmi.
3. Kirim feedback melalui `POST /api/v1/quality/feedback/`. Pilih anonim bila diperlukan; untuk risiko retaliasi sistem membatasi kasus sebagai `restricted`.
4. Feedback duplikat yang masih ditangani ditolak. Gunakan kasus yang sama untuk clarification, action, closure, atau reopen.
5. Feedback hanya ditutup setelah ada bukti tindakan. Identitas pelapor anonim tidak ditampilkan pada portfolio, finding, atau laporan mutu.

## Hasil yang diharapkan

- Mahasiswa hanya melihat profil yang terikat pada akunnya.
- Riwayat studi dan tugas tersedia setelah seed selesai.
- Dashboard program tidak mengekspos identitas atau nilai individu.
- Instrumen mahasiswa tidak pernah memuat controlled answer key.
