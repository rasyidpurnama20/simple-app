# OBE Apps Rebuild v1 — Tahap 0

Tahap 0 adalah fondasi yang sengaja kecil. Tujuannya bukan menjalankan fitur OBE,
melainkan membuktikan bahwa instalasi, login, pemisahan empat peran, dan penyimpanan
data sudah mudah dipahami serta stabil sebelum fitur akademik ditambahkan.

## Mulai

Prasyarat: Docker Desktop atau Docker Engine dengan Docker Compose.

Dari root repositori jalankan satu perintah:

```bash
docker compose -f rebuild/docker-compose.yml up --build
```

Tunggu hingga log menampilkan `Tahap 0 siap`, lalu buka
<http://localhost:8000/accounts/login/>.

| Peran | Username | Password demo lokal |
|---|---|---|
| Prodi | `prodi` | `belajar-tahap0` |
| GPM | `gpm` | `belajar-tahap0` |
| Pengampu | `pengampu` | `belajar-tahap0` |
| Mahasiswa | `mahasiswa` | `belajar-tahap0` |

Password tersebut hanya untuk demo lokal dan jangan digunakan pada server publik.
Perintah mulai di atas sama untuk PowerShell dan Git Bash.

Untuk mengganti password atau port, salin template konfigurasi satu kali:

```text
# Git Bash
cp rebuild/.env.example rebuild/.env

# PowerShell
Copy-Item rebuild/.env.example rebuild/.env
```

Edit `rebuild/.env`, lalu jalankan kembali perintah mulai. File `.env` tidak masuk Git.

## Yang seharusnya terlihat

- Docker hanya menjalankan container `obe-stage0-web` dan `obe-stage0-db`.
- Migration dan pembuatan akun demo berjalan otomatis di container `web`.
- Setelah login, dashboard menampilkan nama serta tujuan peran yang dipakai.
- Dashboard dengan jujur menandai fitur OBE sebagai “belum tersedia”.
- Restart container tidak menghapus akun atau data PostgreSQL.

## Dokumentasi

- [Peta rebuild dan aturan berhenti per tahap](docs/README.md)
- [Tujuan, ruang lingkup, dan kriteria penerimaan](docs/STAGE_0.md)
- [Peran dan batas kewenangan](docs/ROLES.md)
- [Katalog tujuan dan tutorial setiap fitur](docs/FEATURES.md)
- [Tutorial uji pengguna 10–15 menit](docs/USER_TEST.md)
- [Operasi dan pemecahan masalah](docs/TROUBLESHOOTING.md)

Tahap 1 tidak boleh dimulai sebelum pengguna mencoba [checklist penerimaan](docs/USER_TEST.md)
dan menyatakan **“Tahap 0 sudah benar.”**
