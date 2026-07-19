# Tutorial Mahasiswa

## Tujuan

Mahasiswa melihat tugas dan riwayat akademiknya sendiri tanpa memperoleh akses ke data mahasiswa lain.

## Masuk

1. Buka <http://localhost:8000/accounts/login/>.
2. Masuk dengan username `mahasiswa` dan password lokal dari `setup-local.sh`.
3. Akun demo ini dipetakan ke satu identitas mahasiswa sintetis dari fixture compact; tidak ada data mahasiswa produksi.

## Lihat kemajuan pribadi

1. Buka **Kemajuan** atau <http://localhost:8000/me/progress/>.
2. Periksa NIM sintetis, SKS lulus, IPK terhitung, dan daftar hasil studi.
3. Nilai dihitung dari record yang diimpor. Bila mata kuliah atau hasil tidak dikenal, laporkan kepada Pengampu/Prodi dan jangan mengubah data sumber sendiri.

## Kerjakan tugas

1. Buka **Tugas Saya**.
2. Cari **Periksa riwayat studi dan capaian pribadi**.
3. Cocokkan hasil dengan halaman Kemajuan. Gunakan kanal akademik resmi bila memerlukan koreksi.

## Lihat konteks program

Dashboard dan katalog bersifat agregat/program. Mahasiswa boleh melihatnya sebagai konteks, tetapi tidak boleh menyimpulkan posisi mahasiswa lain dari agregat tersebut.

## Hasil yang diharapkan

- Mahasiswa hanya melihat profil yang terikat pada akunnya.
- Riwayat studi dan tugas tersedia setelah seed selesai.
- Dashboard program tidak mengekspos identitas atau nilai individu.
