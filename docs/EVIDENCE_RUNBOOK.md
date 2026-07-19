# Repositori evidence immutable

File disimpan privat pada `<EVIDENCE_ROOT>/<sha[0:2]>/<sha[2:4]>/<sha256>` dengan mode direktori `0700` dan file `0600`. Beberapa manifest boleh merujuk byte identik, tetapi satu academic object/version hanya memiliki satu manifest.

Upload menerapkan batas 25 MiB, allowlist MIME, quota pemilik, klasifikasi, staging file atomik, dan ClamAV INSTREAM pada staging/production. Manifest merekam checksum, ukuran, MIME, filename, owner, objek, periode, versi, klasifikasi, hasil/signature scan, path, dan waktu.

Status hanya bergerak melalui state machine `draft → submitted → verified/rejected`; verified hanya dapat menjadi superseded/archived dan tidak dapat ditimpa/dihapus. Verifikasi status selalu menghitung ulang checksum.

Unduh memerlukan user terautentikasi, object permission, token terikat user+manifest dengan expiry, checksum yang masih cocok, serta audit sukses/ditolak. Aplikasi mengirim `Content-Disposition: attachment` dengan filename yang dibentuk server.

Backup harian memakai `pg_dump` konsisten dan Restic terenkripsi ke repository off-host. Restore per komponen:

```bash
python -m scripts.obe_ops restore --component evidence --snapshot <id>
python manage.py verify_evidence_repository
```

Selective restore menggunakan include Restic untuk content path yang diminta, kemudian inventori/checksum diverifikasi. Full restore wajib menghasilkan kecocokan checksum 100%; mismatch memblokir readiness operasional dan harus diperlakukan sebagai insiden integritas.
