# Penerimaan PR-19–PR-24

## Ringkasan

Batch ini menyelesaikan paket kurikulum sebagai satu aggregate berversi. Cakupan berhenti sebelum lifecycle RPS PR-25.

| PR | Bukti implementasi | Acceptance otomatis |
|---|---|---|
| 19 | lifecycle draft/review/approval/active/archive, immutable active/archive, clone/diff/rollback, paket JSON/CSV dan checksum | lifecycle separation, tamper, idempotency, failed-activation rollback |
| 20 | 5 PL dan 12 CPL dengan deskripsi/bobot/target/effective version dari fixture v5 | exact fixture comparison, count dan global-weight gate |
| 21 | 18 BK, kategori, depth pengetahuan/keterampilan/sikap 1–6, owner | metadata validation, gap/orphan validation |
| 22 | 77 mata kuliah, semester/SKS/status/prasyarat/equivalence dan progress status | exact count, credit gate, passed/repeat/equivalent/remaining |
| 23 | 31 CPMK program yang terpisah dari outcome RPS | exact fixture comparison dan mapping/gap report |
| 24 | PL→CPL→BK→COURSE→CPMK plus CPL→CPMK, bobot 100±0,01, forward/reverse trace | no equal-split, approval reference, over/under/unallocated/orphan/direction/cycle gate |

## Keputusan desain

- Importer menormalisasi signal sumber menjadi bobot proporsional per parent; bobot BK diturunkan dari total `cplDepth`, dan rounding residual diletakkan pada target terakhir sehingga total deterministik 100,0000.
- Metode `derived-proportional` tidak dianggap keputusan akademik sampai reviewer mengisi `approval_reference`.
- Exact source dipertahankan. Validator memblokir aktivasi dataset demo karena 129 SKS wajib serta CPMK22/CPMK27 tanpa inbound mapping.
- Checksum dihitung dari metadata kurikulum, outcome, mata kuliah, dan edge terurut. Import JSON/CSV dengan checksum sama idempoten.
- Aktivasi mengunci seluruh versi program agar dua aktivasi overlap tidak lolos bersamaan.

## Gate otomatis

```bash
ruff check .
ruff format --check .
python manage.py makemigrations --check --dry-run --settings=config.settings.test
pytest
coverage run -m pytest
coverage report --fail-under=85
```

Test utama ada di `tests/test_pr19_pr24.py` dan `tests/test_seed.py`. Rehearsal operator mengikuti `docs/CURRICULUM_RUNBOOK.md`.

## Gate institusi yang belum dapat ditutup di repositori

- keputusan resmi mata kuliah wajib mana yang mengubah total 129 menjadi 126 SKS;
- dasar akademik mapping CPMK22 dan CPMK27;
- tanda tangan/nomor dokumen pengesahan nyata;
- concurrency rehearsal pada PostgreSQL staging dan UAT Prodi/GPM.

Semua poin tersebut blocking untuk aktivasi paket demo, tetapi bukan kekurangan implementasi validator.
