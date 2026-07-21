# Tutorial Uji Pengguna Tahap 0

Perkiraan waktu: 10–15 menit. Lakukan dari root repositori.

## 1. Mulai

```bash
docker compose -f rebuild/docker-compose.yml up --build
```

Lulus bila log menampilkan `Tahap 0 siap` dan tidak berhenti pada traceback. Biarkan
terminal ini terbuka, lalu gunakan terminal kedua untuk langkah berikutnya.

## 2. Periksa dua container

```bash
docker compose -f rebuild/docker-compose.yml ps
```

Lulus bila hanya ada `obe-stage0-web` dan `obe-stage0-db`, keduanya sehat.

## 3. Uji empat peran

Buka <http://localhost:8000/accounts/login/>. Untuk setiap username berikut, gunakan
password `belajar-tahap0`, baca dashboard, lalu klik **Keluar**.

- `prodi` menampilkan **Program Studi (Prodi)**.
- `gpm` menampilkan **Gugus Penjaminan Mutu (GPM)**.
- `pengampu` menampilkan **Pengampu**.
- `mahasiswa` menampilkan **Mahasiswa**.

Lulus bila setiap akun hanya melihat tujuan perannya dan semuanya melihat pemberitahuan
bahwa fitur OBE belum tersedia.

## 4. Uji restart aman

```bash
docker compose -f rebuild/docker-compose.yml restart web
docker compose -f rebuild/docker-compose.yml up --detach --wait
```

Login kembali sebagai `mahasiswa`. Lulus bila password masih bekerja dan dashboard tetap
menampilkan peran Mahasiswa.

## 5. Periksa otomatis

```bash
docker compose -f rebuild/docker-compose.yml exec web python manage.py verify_stage0
docker compose -f rebuild/docker-compose.yml exec web python manage.py test
```

Lulus bila verifikasi menampilkan empat akun siap dan seluruh test sukses.

## 6. Hentikan tanpa menghapus data

```bash
docker compose -f rebuild/docker-compose.yml down
```

Perintah ini menghentikan container tetapi mempertahankan volume PostgreSQL.

## Persetujuan

Jika seluruh langkah sesuai dan alurnya mudah dipahami, beri komentar pada PR:

> Tahap 0 sudah benar.

Jika ada yang berbeda, jangan menyetujui tahap. Catat nomor langkah, akun yang dipakai,
hasil yang terlihat, dan log dari panduan troubleshooting.
