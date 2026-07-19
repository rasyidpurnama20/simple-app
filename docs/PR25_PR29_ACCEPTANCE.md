# Acceptance PR-25–PR-29

| PR | Kriteria utama | Bukti implementasi | Test otomatis |
|---|---|---|---|
| 25 | RPS versioned, draft→GPM→Prodi→published, komentar field, stale guard, immutable snapshot, clone/diff | `learning.models.RPSVersion/RPSFieldComment`, lifecycle dan checksum di `learning.services` | lifecycle, return, concurrent review, stale approval, edit published, clone/diff |
| 26 | CPMK-RPS, Sub-CPMK, indikator observable, mapping CPL/CPMK program, bobot 100% | `CourseOutcome`, `SubOutcome`, `PerformanceIndicator`, `validate_rps` | empty/broken mapping, indikator, dan bobot tervalidasi oleh fixture valid serta variasi invalid |
| 27 | 16 minggu, UTS/UAS, metode/waktu, reschedule, realisasi, planned-vs-actual | `WeeklyPlan`, `reschedule_week`, `record_week_execution`, `planned_vs_actual` | exact week/type/method/time/date dijalankan pada lifecycle test |
| 28 | Instrumen dan blueprint, mapping, total 100%, publish sebelum pengajaran, evidence | `AssessmentInstrument`, `assessment_plan_report`, `publish_assessment_plan` | blueprint/mapping/evidence/jadwal/bobot dan snapshot diuji |
| 29 | Rubrik/butir/kriteria/level, controlled key, blind/second marker, regrade versi baru | `Rubric*`, `AssessmentItem`, `CriterionScore`, grading/moderation/regrade services | bobot/overlap, redaksi key, trace, second marker, immutable rubric, regrade diuji |

Gate lokal:

```bash
pytest tests/test_pr25_pr29.py tests/test_seed.py
python manage.py makemigrations --check --dry-run
python tests/test_architecture.py
```

Acceptance institusi tetap memerlukan UAT dengan aktor aktual, kalender resmi, dokumen RPS yang disahkan, kebijakan moderasi, dan golden grade calculation. Seed `published-demo` tidak merupakan approval institusi.
