# Runbook deployment reproducible

## Artefak dan host

OBE Server memakai `deploy/server/compose.yml`; Exam Edge memakai `deploy/exam-edge/compose.yml`. Seluruh image wajib berbentuk `registry/image@sha256:<64-hex>`. Tag mutable seperti `latest` ditolak oleh preflight `obe_ops`.

Host baru diprovision dengan:

```bash
ansible-playbook -i deploy/ansible/inventory.yml deploy/ansible/site.yml
```

Role Ansible membuat user/UID tetap `20001`, direktori terpisah untuk database, evidence, queue, cache, observability, config, backup, dan TLS; memasang Docker, firewall deny-by-default, Restic, node exporter, certificate, backup timer, release bundle, lalu deployment. Kunci TLS, environment backup, dan secret SOPS hanya disuplai operator melalui variable source privat.

## Persiapan deployment

1. Salin `deploy/server/images.env.example` menjadi `.env`, isi digest nyata, serta path absolut.
2. Salin `deploy/env/production.env.example` menjadi `deploy/env/production.env` dan sesuaikan nonsecret config.
3. Materialisasikan SOPS ke `OBE_SECRET_DIR` sesuai [runbook secret](SECRETS_RUNBOOK.md).
4. Pastikan certificate ada sebagai `fullchain.pem` dan `privkey.pem` di `${OBE_DATA_ROOT}/tls`.

## Perintah idempotent

```bash
# Pull dan converge seluruh service, lalu tunggu health/readiness
python -m scripts.obe_ops deploy

# Migration eksplisit
python -m scripts.obe_ops migrate

# Rollback satu image immutable
python -m scripts.obe_ops rollback --image registry.example/obe@sha256:<digest>

# Restore satu komponen dari Restic; database otomatis di-pg_restore
python -m scripts.obe_ops restore --component database --snapshot <snapshot-id>
python -m scripts.obe_ops restore --component evidence --snapshot <snapshot-id>

# Rotasi secret
python -m scripts.obe_ops rotate-secret --secret-type django-secret-key --secret-directory /srv/obe/config/secrets

# Smoke test
python -m scripts.obe_ops smoke-test --base-url https://obe.example.invalid
```

Gunakan `--dry-run` untuk melihat rencana deterministik tanpa mengubah layanan.

## Maintenance dan rollback

Aktifkan maintenance secara persisten dengan membuat `/srv/obe/config/maintenance`; `healthz` tetap 200 sedangkan endpoint lain, termasuk readiness, menjadi 503 dengan `Retry-After`. Hapus sentinel setelah migration/restore dan smoke test lulus. Rollback image tidak otomatis menjalankan migration backward; hanya jalankan backward migration yang telah lolos pemeriksa reversibility.

## Rebuild staging dan rehearsal

Acceptance staging dijalankan berurutan pada host kosong: dua kali Ansible (run kedua tanpa drift material), deploy, smoke test, reboot host, smoke test, redeploy image sama, rollback satu digest, restore database/config/evidence, lalu verifikasi checksum evidence. Simpan digest image, checksum config terenkripsi, health state, waktu RPO/RTO, dan output tanpa secret sebagai bukti. Restart policy dan timer `Persistent=true` memastikan layanan/backup pulih setelah reboot.
