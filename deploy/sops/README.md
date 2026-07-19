# SOPS untuk secret runtime

Repositori hanya menyimpan contoh terenkripsi dan public recipient. Private key `age` hanya boleh berada di password manager operator atau host deployment berwenang, tidak di image, CI artifact, backup metadata, maupun repositori.

1. Salin `.sops.yaml.example` menjadi `.sops.yaml`, lalu ganti recipient dengan public key institusi.
2. Buat berkas dari `secrets.example.enc.yaml`, isi nilai melalui `sops edit`, dan commit hanya hasil terenkripsi.
3. Pada host berwenang, materialisasikan ke tmpfs/runtime secret directory:

   ```bash
   ./scripts/materialize_sops_secrets.sh production deploy/sops/production.enc.yaml /run/obe-secrets
   ```

4. Mount file sebagai read-only dan gunakan variabel `*_FILE`. Hapus file materialisasi ketika deployment selesai atau host dipensiunkan.

Jangan memakai contoh `ENC[...]` sebagai secret nyata. Prosedur rotasi, overlap, revokasi, audit, dan respons kebocoran ada di [runbook secret](../../docs/SECRETS_RUNBOOK.md).
