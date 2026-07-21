# Operasi dan Pemecahan Masalah Tahap 0

## Melihat status dan log

```bash
docker compose -f rebuild/docker-compose.yml ps --all
docker compose -f rebuild/docker-compose.yml logs --tail=100 web db
```

| Gejala | Arti dan tindakan |
|---|---|
| `No migrations to apply` | Sukses; schema sudah terbaru. |
| Port `8000` sudah dipakai | Salin `.env.example` menjadi `.env`, ubah `STAGE0_PORT=8080`, lalu buka port 8080. |
| `db` tidak sehat | Pastikan Docker memiliki ruang disk, lalu lihat log `db`. |
| Login ditolak | Pastikan username huruf kecil dan password sesuai variabel `STAGE0_DEMO_PASSWORD`. |
| `web` restart berulang | Lihat traceback pertama pada log `web`; migration/seed berhenti secara jelas bila gagal. |
| Tampilan lama masih terbuka | Pastikan URL memakai port Tahap 0 dan muat ulang browser. |

Contoh memakai port lain dari root repositori:

```text
# Git Bash
cp rebuild/.env.example rebuild/.env

# PowerShell
Copy-Item rebuild/.env.example rebuild/.env
```

Ubah `STAGE0_PORT` di `rebuild/.env`, kemudian jalankan perintah mulai biasa.

## Stop dan start biasa

```bash
docker compose -f rebuild/docker-compose.yml down
docker compose -f rebuild/docker-compose.yml up --build
```

Data tetap ada karena volume tidak dihapus.

## Reset total khusus data demo Tahap 0

Perintah berikut menghapus seluruh database **Tahap 0**. Gunakan hanya jika memang ingin
mengulang demo Tahap 0 dari kosong; perintah ini tidak menyentuh stack aplikasi lama.

```bash
docker compose -f rebuild/docker-compose.yml down --volumes
```

Target harus terlihat sebagai project `obe-stage0`. Jangan menjalankan variasi perintah
penghapusan volume pada Compose aplikasi lama.
