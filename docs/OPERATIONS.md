# Operasi, Backup, Restore, dan Rollback

## Deploy

1. Isi secret melalui SOPS sesuai [runbook](SECRETS_RUNBOOK.md); jangan commit plaintext.
2. Set `OBE_IMAGE` ke image immutable dengan digest.
3. Jalankan backup pra-rilis.
4. `docker compose pull && docker compose up -d`.
5. Jalankan migration, `healthz`, `readyz`, smoke test, dan rekonsiliasi outbox.
6. Aktifkan fitur bertahap melalui feature flag.

## Backup harian

- `pg_dump --format=custom` database.
- Snapshot evidence, config terenkripsi, signing metadata, dan audit.
- Hitung SHA-256 seluruh artefak dan salin ke storage off-host.
- Simpan record count, waktu, versi aplikasi, checksum ciphertext, serta versi secret pada manifest backup. Jangan simpan nilai secret, decrypted file, environment dump, atau hash plaintext secret.

## Restore rehearsal

1. Provision host berbeda dengan Ansible.
2. Restore PostgreSQL ke database kosong.
3. Restore evidence sesuai content-addressed path.
4. Verifikasi checksum 100%, migration state, record count, audit chain, dan signed bundle metadata.
5. Jalankan smoke/UAT minimum dan catat RPO/RTO aktual.

## Rollback

- Matikan feature flag bermasalah terlebih dahulu.
- Rollback image ke digest sebelumnya.
- Jalankan migration backward hanya bila migration plan menyatakan aman.
- Data correction memakai forward-fix dan audit; jangan menghapus audit/outbox.

## Insiden

P1/P2 mengaktifkan on-call dan communication plan. Catat correlation ID, dampak, timeline, mitigasi, dan postmortem tanpa menyalahkan individu. AI, export, integration write, notification, analytics berat, dan Secure Exam sync memiliki kill switch terpisah.
