# Instalasi lokal OBE Apps

## Cara tercepat

Pastikan Docker Desktop atau Docker Engine sedang aktif, lalu dari root repositori jalankan satu perintah berikut melalui Git Bash, WSL, atau terminal Linux/macOS:

```bash
./scripts/quickstart.sh
```

Skrip akan melakukan seluruh langkah berikut secara otomatis:

1. memeriksa Docker dan Docker Compose;
2. membuat atau memperbaiki `.env` lokal;
3. membangun satu image aplikasi bersama untuk init, web, worker, dan beat;
4. menjalankan migration dan seed melalui service `init` satu kali;
5. menjalankan web/worker/beat hanya jika init berhasil;
6. membangun dan menjalankan Nginx;
7. memvalidasi konfigurasi dan health check Nginx; dan
8. menampilkan URL, username, password, dan perintah bantuan.

Image aplikasi memakai entrypoint absolut `/usr/local/bin/obe-entrypoint` dan menormalisasi CRLF saat build. Karena itu checkout Windows tidak memerlukan `dos2unix`, perubahan permission, atau konfigurasi Git manual. Nginx juga dibangun ke image lokal tanpa bind mount/directory sharing.

Jangan mencampur quickstart dengan langkah instalasi Compose manual. Untuk memperbarui atau memulihkan instalasi, gunakan urutan tunggal berikut:

```bash
git pull
./scripts/quickstart.sh --clean
```

Service `init` otomatis menjalankan `python manage.py migrate --noinput`. Pesan `No migrations to apply` berarti database sudah terbaru dan merupakan kondisi normal. GitHub Actions memeriksa kelengkapan/reversibilitas migration saat PR dan merge, tetapi database Docker lokal hanya dapat diperbarui oleh service `init` di komputer tempat aplikasi berjalan.

Untuk memahami fungsi `db`, `valkey`, `rabbitmq`, `init`, `web`, `worker`, `beat`, dan `nginx` beserta alur komunikasinya, baca [panduan delapan container Docker Compose](COMPOSE_CONTAINERS.md).

Buka URL **Halaman login** yang dicetak setelah pesan `OBE Apps siap` muncul. URL default-nya <http://localhost:8000/accounts/login/>.

## Akun demo

| Peran | Username | Panduan penggunaan |
|---|---|---|
| Prodi | `prodi` | [Tutorial Prodi](tutorials/prodi.md) |
| GPM | `gpm` | [Tutorial GPM](tutorials/gpm.md) |
| Pengampu | `pengampu` | [Tutorial Pengampu](tutorials/pengampu.md) |
| Mahasiswa | `mahasiswa` | [Tutorial Mahasiswa](tutorials/mahasiswa.md) |

Keempat akun memakai password lokal yang sama dan ditampilkan oleh quickstart. Jika output terminal sudah tertutup, buka file `.env` lalu lihat nilai `OBE_DEMO_PASSWORD`. Jangan bagikan atau commit file tersebut. Quickstart/seed menyinkronkan ulang password akun demo dengan nilai `.env`, termasuk ketika password lokal berubah.

Langkah login:

1. tunggu sampai quickstart menampilkan `OBE Apps siap`;
2. buka URL **Halaman login** yang dicetak;
3. masukkan salah satu username pada tabel dan password `OBE_DEMO_PASSWORD`; dan
4. pilih tutorial peran untuk skenario penggunaan pertamanya.

## Memperbaiki percobaan yang gagal

Jalankan:

```bash
./scripts/quickstart.sh --clean
```

Opsi ini menghentikan dan membuat ulang container, tetapi **tidak menghapus data di volume Docker**. Quickstart juga memperbaiki kasus `.env` lama dengan `OBE_DEMO_PASSWORD` kosong atau kurang dari 16 karakter.

Jika port `8000` sudah dipakai, pilih port lain tanpa mengedit konfigurasi:

```bash
./scripts/quickstart.sh --port 8080
```

Setelah itu buka <http://localhost:8080>. Pilihan port hanya berlaku untuk proses tersebut; set `OBE_HTTP_PORT` di `.env` jika ingin menyimpannya.

Jika belum berhasil, periksa pesan yang ditampilkan. Penyebab umum:

| Pesan | Tindakan |
|---|---|
| `Docker belum terpasang` | Pasang Docker Desktop/Engine dan buka terminal baru. |
| `Docker tidak aktif` | Jalankan Docker Desktop atau daemon Docker. |
| `Docker Compose tidak ditemukan` | Aktifkan plugin Compose atau perbarui Docker Desktop. |
| `Aplikasi belum siap` | Lihat ringkasan log yang otomatis dicetak, lalu jalankan quickstart dengan `--clean`. |
| Port `8000` sudah dipakai | Jalankan `./scripts/quickstart.sh --port 8080`. |
| `Nginx gagal memuat konfigurasi` | Lihat log yang otomatis dicetak; quickstart tidak akan lagi menyatakan aplikasi siap jika proxy gagal. |
| `exec ./scripts/entrypoint.sh: no such file or directory` | Tarik versi terbaru lalu jalankan quickstart dengan `--clean`. Versi baru memakai entrypoint absolut dan menormalisasi CRLF di image. |
| `No migrations to apply` | Tidak perlu tindakan; migration otomatis berhasil dan database sudah terbaru. Tunggu pesan `OBE Apps siap`. |
| Service `init` gagal | Jalankan `docker compose logs init`; quickstart juga mencetak log init otomatis ketika startup gagal. |
| `Forbidden (403) CSRF verification failed` | Pastikan URL sama dengan yang dicetak quickstart, lalu muat ulang halaman login agar token baru dibuat. Jalankan `./scripts/quickstart.sh --clean` bila stack berasal dari versi lama. Jangan menonaktifkan CSRF. |
| Login ditolak setelah password `.env` berubah | Jalankan kembali `./scripts/quickstart.sh`; seed akan menyinkronkan seluruh akun demo. |

## Operasi sehari-hari

```bash
# Lihat status
docker compose ps

# Ikuti log aplikasi
docker compose logs -f web

# Hentikan aplikasi; data tetap ada
docker compose down

# Mulai kembali
./scripts/quickstart.sh
```

Instalasi yang memakai perintah lama `docker-compose` tetap didukung oleh quickstart.

## Reset total (menghapus data lokal)

Gunakan hanya bila Anda benar-benar ingin menghapus database dan semua volume lokal:

```bash
docker compose down --volumes --remove-orphans
./scripts/quickstart.sh
```

Perintah reset total tidak dijalankan otomatis karena data yang sudah ada tidak dapat dipulihkan dari volume yang dihapus.
