# Penerimaan PR-15–PR-18

| PR | Kontrol | Bukti utama | Status |
|---|---|---|---|
| 15 | Registry code/scope/schema/expression/priority/severity/periode/cohort/version; pass/fail/indeterminate; lifecycle maker-checker; immutable active; replay identik | `shared.AcademicRule`, `shared.AcademicDecision`, `shared/academic_rules.py`, migration dan test deterministik/conflict/missing input | Implemented |
| 16 | Package legacy/current, boundary nilai, batas IRS, returning 18 SKS, milestone 3/5/13, syarat program berversi, tepat satu package per cohort/tanggal | `shared.CohortRulePackage`, `shared/rules.py`, importer schema v5 dan boundary tests | Implemented |
| 17 | Explanation lengkap, decision snapshot, authorized override dengan evidence/expiry/maker-checker, banding tujuh state, source tidak berubah, audit | `DecisionOverride`, `AcademicAppeal`, service workflow, replay dan negative tests | Implemented |
| 18 | Validasi field/range/weight/date/checksum/evidence/duplicate/orphan, severity dan issue workflow, optimistic lock, official-use gate | `quality/integrity.py`, `IntegrityValidationRun`, enhanced `IntegrityIssue`, revalidation/gate tests | Implemented |

## Hasil otomatis

- Rule/package seed schema v5 idempoten: 11 rule dan 2 package.
- Rule aktif dan package aktif immutable; perubahan memakai versi baru.
- Input/rule/version yang sama menghasilkan decision hash dan trace yang sama.
- Override/appeal self-approval dan actor tanpa otorisasi ditolak.
- Blocking issue tetap menutup gate sampai diverifikasi independen.
- Migration maju/mundur, architecture gate, lint, type check, seluruh test, dan critical coverage wajib lulus.

Golden calculation institusi, rekonsiliasi SIA, dan UAT maker-checker dengan actor nyata tetap menjadi gate staging sebelum keputusan dipakai pada proses akademik resmi.
