# Acceptance PR-30–PR-33 dan Dataset v5 Tahap 3

## Cakupan

| PR | Kontrol utama | Bukti otomatis |
|---|---|---|
| PR-30 | kelas paralel, checksum blueprint/soal, review GPM, approval Prodi, kebijakan strict-same-question, analisis disparity | `test_pr30_parallel_exam_requires_equivalence_approval_and_flags_disparity` |
| PR-31 | raw/max/normalized, batas 100, attempt, paket nilai historis, kategori kompetensi, best attempt, syarat C/B | `test_pr31_grade_normalization_history_best_attempt_and_requirements` |
| PR-32 | roster dan IRS, denominator hanya aktivitas terlaksana, batas UAS 75%, official override maker-checker, snapshot alasan | `test_pr32_attendance_eligibility_uses_held_denominator_irs_and_override` |
| PR-33 | draft/final/reopen, deadline/late, group member, checksum receipt, feedback terpetakan, perubahan nilai maker-checker, revision evidence | `test_pr33_submission_receipt_feedback_and_score_revision_maker_checker`, `test_pr33_revises_rejected_evidence_as_a_new_record` |
| Tahap 3 | seluruh offering, RPS/outcome/Sub-CPMK/indikator/minggu, rubrik, dan assessment plan v5 | `test_stage3_imports_all_operational_rows_idempotently` dan acceptance full-file |

## Gate kelas paralel

1. Set UTS/UAS dibuat per kelas dan menyimpan checksum blueprint serta soal.
2. Soal berbeda wajib mempunyai alasan. Coverage dan difficulty harus ekuivalen.
3. GPM mereview; aktor Prodi yang berbeda menyetujui. Question set tidak dapat dirilis sebelum approval.
4. `strict_same_question=true` memblokir soal berbeda walaupun equivalence report tersedia.
5. Rerata kelas dibandingkan setelah ujian. Selisih di atas threshold menghasilkan flag mutu, bukan perubahan nilai otomatis.

## Gate nilai dan eligibility

- Normalisasi menyimpan raw, maksimum, hasil, attempt, paket aturan, versi, kategori kompetensi, dan calculation trace. Bonus boleh dicatat pada raw, tetapi normalized dibatasi 100.
- Nilai historis mempertahankan letter/point dan paket aturan sumber; tidak dikonversi ke skala cohort saat ini.
- Aktivitas `cancelled` dan `exempt` tidak menjadi denominator. `present`, `late`, `permit`, dan `sick` dihitung hadir sesuai aturan saat ini.
- Roster aktif dan IRS approved wajib tersedia. Setiap evaluasi UAS menghasilkan snapshot persen, count, activity ID, reason code, rule version, dan source version.
- Override harus mempunyai reason code, alasan, evidence, maker, checker berbeda, serta jejak audit.

## Gate submission dan perubahan nilai

- Draft dapat diganti pada attempt yang sama. Final menyimpan timestamp dan SHA-256 receipt, lalu immutable.
- Reopening final hanya melalui aksi resmi beralasan. Finalisasi setelah deadline ditolak kecuali kebijakan late eksplisit dipakai; flag `late` tetap tersimpan.
- Group submission memvalidasi instrumen dan daftar anggota. Evidence ID duplikat ditolak.
- Feedback harus menunjuk kriteria atau outcome dan memuat teks atau file.
- Perubahan score published dibuat sebagai `ScoreRevision`; maker tidak boleh menjadi checker. Approval membuat score `regraded` baru dengan `supersedes_score`, recalculation, notification key, dan audit before/after.

## Menjalankan acceptance

```bash
pytest -q tests/test_pr30_pr33.py
python manage.py makemigrations --check --dry-run
ruff check .
```

Untuk file v5 lengkap:

```bash
OBE_FULL_SAMPLE_PATH=/path/ke/sample-data-2020-2026-obe-spec-v5.json \
  pytest -q tests/test_sample_import.py -k full_sample
```

Laporan import harus menunjukkan `source == imported` untuk `course_offerings`, `rps_versions`, `course_outcomes`, `sub_outcomes`, `indicators`, `weekly_plans`, `assessment_plans`, dan `rubrics`; tidak boleh ada `not_in_current_import_scope` untuk kelompok tersebut.
