# Acceptance PR-34–PR-39 — Attainment sampai Tindak Lanjut Mutu

## Cakupan

| PR | Acceptance utama | Bukti otomatis |
|---|---|---|
| 34 | Formula distribution berversi, pemisahan maker/reviewer/approver, skala 0–100, blocking gate, snapshot dan controlled recalculation | `test_pr34_formula_calculation_recalculation_and_fail_closed`, `test_pr34_formula_validation_and_separation_of_duties` |
| 35 | Rantai outcome→mata kuliah→asesmen→bukti→nilai→attainment→CQI dapat ditelusuri maju/balik; gate terpisah, gap tetap terlihat, dan akses terscope | `test_pr35_forward_backward_trace_keeps_gaps_and_permissions`, `test_pr37_provus_cqi_effectiveness_ineffective_risk_and_api` |
| 36 | Portfolio student/course/program berasal dari data terverifikasi, lifecycle maker-checker, regenerasi, checksum, HTML/CSV/PDF reproducible | `test_pr36_portfolio_lifecycle_reproducible_export_and_regeneration` |
| 37 | Provus menyimpan target/gap/denominator/coverage/confidence; CQI action dapat effective, ineffective, accepted-risk, dan reopened | `test_pr37_provus_cqi_effectiveness_ineffective_risk_and_api` |
| 38 | PPEPP dan laporan semester memakai empat aktor, source version, checksum, correction cycle, serta export reproducible | `test_pr38_ppepp_report_four_actor_workflow_export_and_correction` |
| 39 | Feedback anonim/restricted, deduplikasi, verifikasi, action, penutupan/reopen, privacy, dan audit akses | `test_pr39_feedback_anonymous_duplicate_restricted_lifecycle_and_audit` |

## Invariant fail-closed

1. Formula aktif immutable dan hanya aktif setelah maker, reviewer, dan approver berbeda.
2. Attainment tidak menghasilkan angka bila score belum published, evidence belum verified, source hilang/duplikat/unallocated, path berbeda, atau integrity gate mengirim blocker.
3. Recalculation selalu membuat snapshot baru, menyimpan diff dan alasan, serta menandai snapshot lama `superseded`.
4. Node mata kuliah serta gate curriculum/learning/RPS/assessment/execution/score/attainment/CQI eksplisit; gap/orphan tetap berada dalam trace response dan tidak dihapus.
5. Portfolio dan laporan yang belum lengkap tidak dapat approved/published.
6. Identitas pelapor anonim tidak disimpan pada record feedback. Kasus retaliation risk otomatis `restricted`, dan setiap pembukaan kasus diaudit.

## Menjalankan acceptance

```bash
pytest -q tests/test_pr34_pr39.py
python manage.py makemigrations --check --dry-run
python tests/test_architecture.py
```

Acceptance dataset penuh tetap wajib karena Tahap 5 memakai data yang diimpor pada Tahap 4:

```bash
pytest -q tests/test_sample_import.py -k full_sample
```

## Gate lingkungan

Golden calculation institusi, sign-off target CPL, assignment TPMF aktual, dokumen evidence fisik, policy anonimitas/retaliasi, dan template laporan resmi tetap harus disahkan pada staging. Record sumber `verified` yang hanya memiliki metadata pada dataset tetap berstatus aplikasi `submitted`, sehingga tidak boleh otomatis masuk portfolio resmi.
