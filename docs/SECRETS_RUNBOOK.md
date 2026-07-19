# Runbook lingkungan dan secret

## Profil yang terpisah

| Profil | Settings | Sumber secret | Tujuan |
|---|---|---|---|
| local | `config.settings.local` | `.env` privat | pengembangan |
| test | `config.settings.test` | environment CI nonproduksi | pengujian |
| staging | `config.settings.staging` | SOPS → runtime file | validasi rilis |
| production | `config.settings.production` | SOPS → runtime file | layanan utama |
| exam-edge | `config.settings.exam_edge` | SOPS → runtime file di VLAN ujian | ujian luring |

`OBE_ENV` wajib sama dengan settings module. Profil terkelola berhenti saat startup bila host, mode TLS, URL broker/gateway, PostgreSQL, secret, atau timestamp rotasi tidak valid. `.env` hanya pernah dibaca oleh local/test.

## Inventaris dan masa rotasi maksimum

| Secret | Variabel file | Maksimum | Overlap aman |
|---|---|---:|---|
| password database | `DATABASE_URL_FILE` | 90 hari | role/password DB lama dan baru |
| session/signing Django | `OBE_SECRET_KEY_FILE` | 90 hari | `OBE_SECRET_KEY_FALLBACKS_FILE` |
| API key LiteLLM | `LITELLM_API_KEY_FILE` | 60 hari | dua key aktif di gateway |
| password RabbitMQ | runtime secret `rabbitmq_password` | 90 hari | user/password broker lama dan baru |
| signing key Exam Edge | `OBE_EXAM_SIGNING_KEY_FILE` | 90 hari | `OBE_EXAM_SIGNING_KEY_FALLBACKS_FILE` |
| credential sync Exam Edge | `OBE_EXAM_SYNC_TOKEN_FILE` | 30 hari | token lama dan baru pada endpoint sync |

Setiap deployment juga membawa `<NAMA>_ROTATED_AT` berformat ISO-8601 dengan zona waktu. Nilai ini metadata, bukan secret.

## Dekripsi dan akses

Private key `age` hanya tersedia untuk operator/host deployment berwenang. Gunakan alur di [`deploy/sops/README.md`](../deploy/sops/README.md), materialisasikan ke tmpfs dengan mode direktori `0700` dan file `0600`, lalu mount read-only. Jangan mendekripsi ke working tree atau CI artifact.

## Rotasi tanpa downtime

Generator berikut membuat nilai baru tanpa menampilkannya serta memindahkan nilai aktif menjadi `.previous`:

```bash
python scripts/rotate_secret.py django-secret-key --directory /run/obe-secrets
```

Ganti jenis dengan `database-password`, `litellm-api-key`, `exam-signing-key`, atau `exam-sync-token`.

1. Buat secret baru, perbarui SOPS, dan aktifkan versi baru pada layanan upstream bila ada.
2. Pertahankan versi sebelumnya: gunakan fallback file untuk Django/Exam signature; pertahankan dua credential di PostgreSQL, LiteLLM, atau endpoint sync.
3. Rolling restart instance. Instance baru menulis/sign dengan current, tetapi masih membaca/verifikasi previous.
4. Verifikasi readiness, login/session lama, query DB, panggilan AI, bundle ujian lama, dan sync.
5. Setelah seluruh instance serta workload lama selesai, cabut versi sebelumnya:

   ```bash
   python scripts/rotate_secret.py django-secret-key --directory /run/obe-secrets --revoke-previous
   ```

6. Perbarui timestamp rotasi, commit ciphertext SOPS baru, dan simpan bukti keberhasilan tanpa nilai rahasia.

Untuk password DB, buat credential baru terlebih dahulu, ubah `DATABASE_URL_FILE`, rolling restart, lalu cabut credential lama. Untuk key LiteLLM/token sync, buat dua key aktif di upstream selama overlap. Rotasi darurat melewati masa overlap hanya bila credential sudah terindikasi bocor; konsekuensinya session atau pekerjaan lama dapat dibatalkan.

## Revokasi dan insiden

Jika secret terekspos: blokir akses, cabut di upstream, rotasi seluruh turunan, cari correlation ID yang terdampak, jalankan gitleaks, dan dokumentasikan waktu/owner/dampak. Jangan menyalin nilainya ke issue, chat, log, hasil test, tracing, payload Celery, manifest backup, atau postmortem.

Log aplikasi, response error, dan atribut tracing memakai redaksi berlapis. Backup hanya boleh menyimpan nama secret, versi/rotated-at, checksum ciphertext, dan status restore—tidak pernah plaintext atau hash yang dapat digunakan untuk menebak secret.
