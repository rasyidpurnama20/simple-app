# Instalasi lokal OBE Apps

## Cara tercepat

Pastikan Docker Desktop atau Docker Engine sedang aktif, lalu dari root repositori jalankan:

```bash
./scripts/quickstart.sh
```

Skrip akan melakukan seluruh langkah berikut secara otomatis:

1. memeriksa Docker dan Docker Compose;
2. membuat atau memperbaiki `.env` lokal;
3. membangun dan menjalankan seluruh service di background;
4. menunggu health check berhasil; dan
5. menampilkan URL, username, password, dan perintah bantuan.

Buka <http://localhost:8000> setelah pesan `OBE Apps siap` muncul.

## Akun demo

| Peran | Username |
|---|---|
| Prodi | `prodi` |
| GPM | `gpm` |
| Pengampu | `pengampu` |
| Mahasiswa | `mahasiswa` |

Keempat akun memakai password lokal yang ditampilkan oleh quickstart. Password juga tersimpan di `OBE_DEMO_PASSWORD` dalam file `.env` yang tidak di-commit.

## Memperbaiki percobaan yang gagal

Jalankan:

```bash
./scripts/quickstart.sh --clean
```

Opsi ini menghentikan dan membuat ulang container, tetapi **tidak menghapus data di volume Docker**. Quickstart juga memperbaiki kasus `.env` lama dengan `OBE_DEMO_PASSWORD` kosong atau kurang dari 16 karakter.

Jika belum berhasil, periksa pesan yang ditampilkan. Penyebab umum:

| Pesan | Tindakan |
|---|---|
| `Docker belum terpasang` | Pasang Docker Desktop/Engine dan buka terminal baru. |
| `Docker tidak aktif` | Jalankan Docker Desktop atau daemon Docker. |
| `Docker Compose tidak ditemukan` | Aktifkan plugin Compose atau perbarui Docker Desktop. |
| `Aplikasi belum siap` | Lihat ringkasan log yang otomatis dicetak, lalu jalankan quickstart dengan `--clean`. |
| Port `8000` sudah dipakai | Hentikan aplikasi lain pada port 8000, lalu ulangi quickstart. |

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
