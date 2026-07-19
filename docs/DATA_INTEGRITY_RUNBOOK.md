# Runbook Integritas Data Akademik

## Gate resmi

Data dengan `blocking` issue hanya boleh dipakai untuk publikasi, attainment, eligibility, kelulusan, laporan mutu, atau sinkronisasi resmi setelah status `verified`. Status `resolved` dan `accepted-risk` belum membuka gate.

## Pemeriksaan deterministik

Validator PR-18 memeriksa field wajib, identifier, SKS, semester, nilai/bobot 0–100, total bobot 100%, periode efektif, checksum, bukti wajib, duplicate, dan orphan reference. Setiap finding memiliki reason code, impact, owner, evidence, source snapshot, checksum, dan fingerprint idempoten.

Tiga severity:

- `blocking`: penggunaan resmi dihentikan;
- `warning`: wajib direview sebelum approval;
- `information`: catatan nonblocking yang tetap dapat ditelusuri.

## Workflow issue

```text
open → assigned/investigating → resolved → verified
open/investigating → accepted-risk → reopened → investigating
resolved → reopened
```

Setiap update memakai optimistic `lock_version`. Update stale ditolak agar koreksi bersamaan tidak saling menimpa. `accepted-risk` wajib beralasan dan tetap memblokir keluaran resmi. Finding yang muncul kembali setelah resolved/verified otomatis menjadi `reopened`.

## Prosedur koreksi

1. Jalankan validator dan catat validation run/checksum.
2. Tetapkan owner serta due date untuk setiap finding.
3. Koreksi record sumber melalui workflow domain; jangan mengedit source snapshot issue.
4. Pindahkan issue ke `resolved` beserta ringkasan koreksi.
5. Jalankan revalidation terhadap sumber terbaru.
6. Checker independen memindahkan issue ke `verified` hanya bila finding tidak muncul lagi.
7. Jalankan gate penggunaan resmi sebelum publikasi atau sinkronisasi.

## Rollback

Jika revalidation menghasilkan finding yang sama, pertahankan gate, pindahkan issue ke `reopened`, batalkan publication/sync job, dan gunakan checksum validation run untuk menentukan versi sumber terakhir yang diketahui aman.
