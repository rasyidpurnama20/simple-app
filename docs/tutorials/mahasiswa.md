# Tutorial Mahasiswa

## Tujuan

Mahasiswa melihat tugas dan riwayat akademiknya sendiri tanpa memperoleh akses ke data mahasiswa lain.

## Masuk

1. Buka <http://localhost:8000/accounts/login/>.
2. Gunakan reset kredensial bila diperlukan dan selesaikan MFA jika akun mengaktifkannya. Sistem menolak ID mahasiswa lain walaupun URL diubah manual.
3. Masuk dengan username `mahasiswa` dan password lokal dari `setup-local.sh`.
4. Akun demo ini dipetakan ke satu identitas mahasiswa sintetis dari fixture compact; tidak ada data mahasiswa produksi.

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

## Hasil yang diharapkan

- Mahasiswa hanya melihat profil yang terikat pada akunnya.
- Riwayat studi dan tugas tersedia setelah seed selesai.
- Dashboard program tidak mengekspos identitas atau nilai individu.
- Instrumen mahasiswa tidak pernah memuat controlled answer key.
