# Runbook Aturan dan Keputusan Akademik

## Tujuan

Runbook ini mencakup PR-15–PR-17: registry aturan berversi, package cohort, decision snapshot, override, dan banding. Seluruh evaluasi bersifat read-only terhadap data sumber.

## Lifecycle rule

1. Prodi membuat versi `draft` dengan `code`, scope, schema input, expression, priority, severity, periode efektif, dan cohort.
2. Reviewer yang berbeda memindahkan rule ke `reviewed` dan mencatat review note.
3. Checker yang bukan maker mengaktifkan versi. Versi aktif sebelumnya dengan code yang sama menjadi `retired`.
4. Versi aktif immutable. Perubahan expression, schema, priority, scope, atau periode harus menjadi versi baru.
5. Conflict priority, rule nonaktif, dan input hilang diproses fail-closed; input hilang menghasilkan `indeterminate`, bukan tebakan.

## Package cohort

Seed schema v5 menyediakan:

- `LEGACY-ABCDE` untuk cohort 2020–2023;
- `CURRENT-AABBC` mulai cohort 2024.

Resolver mewajibkan tepat satu package untuk kombinasi cohort dan tanggal keputusan. Skala nilai, batas IRS, milestone kemajuan, syarat 144/126/18 SKS, PKL, KKN, TA 6 SKS, nilai TA minimum B, dan kemampuan Inggris 400 disimpan bersama versinya. Keputusan historis selalu menunjuk package yang dipakai saat keputusan dibuat.

## Decision snapshot dan replay

`evaluate_and_record` menyimpan rule/version, package, input snapshot, source versions, evidence rows, trace, explanation, input hash, dan decision hash. Pemanggilan dengan rule, objek, serta input yang sama idempoten. `replay_decision` menghitung ulang snapshot dan menolak mismatch.

Keputusan blocking harus menampilkan:

- rule code dan version;
- field aktual dan kondisi yang gagal;
- source version pada evidence row;
- langkah perbaikan pada explanation.

## Override

1. Pastikan caller lulus scoped permission service.
2. Override hanya dapat diajukan untuk outcome `fail`.
3. Isi reason code, alasan, dokumen evidence immutable, dampak, dan masa berlaku.
4. Checker yang berbeda memilih approve atau reject.
5. Override disimpan sebagai objek terpisah. Input snapshot dan data sumber tidak berubah.
6. Override kedaluwarsa tidak mengubah effective outcome.

## Banding

State yang diizinkan: `submitted`, `reviewed`, `information-needed`, `approved`, `rejected`, `expired`, dan `closed`. Transisi di luar state machine, reviewer yang sama dengan pemohon, atau banding kedaluwarsa ditolak. Seluruh transisi mempunyai audit dan referensi ke decision asal.

## Pemeriksaan operasional

```bash
python manage.py import_obe_sample
pytest tests/test_pr15_pr18.py -q
python manage.py makemigrations --check --dry-run
```

Sebelum mengaktifkan versi baru, arsipkan hasil golden replay untuk boundary, missing input, dan conflict case di acceptance evidence feature flag/rilis.
