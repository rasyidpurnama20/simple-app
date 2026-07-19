# Dataset Sintetis OBE v5

## Import bawaan

`fixtures/sample-data-2020-2026-obe-spec-v5.compact.json` memuat katalog lengkap schema v5: 5 PL, 12 CPL, 18 bahan kajian, 31 CPMK, 77 mata kuliah, seluruh pemetaan, agregat capaian mata kuliah, serta empat riwayat mahasiswa sintetis representatif. Untuk bagian governance dan learning/assessment yang tidak disalin ke fixture compact, importer memakai irisan kanonik file v5 lengkap: 2 package cohort, 11 academic rule, dan RPS `MIK1624101` beserta outcome, 16 minggu, enam instrumen, dan dua rubrik.

File v5 lengkap dapat diberikan melalui `--path`; package dan rule dari file tersebut menjadi sumber utama. Fallback kanonik hanya dipakai untuk fixture compact dan mempunyai nilai yang sama dengan `academicRuleRegistry` v5.

## Menjalankan import

```bash
python manage.py import_obe_sample
```

Importer bersifat transaksional dan idempotent. Menjalankannya kembali memperbarui record dengan identifier yang sama tanpa menggandakan data.

Jika volume lokal masih memuat seed generik lama (`program_code=IF` tanpa provenance), importer menandainya `archived`. Record tidak dihapus, tetapi katalog pengguna hanya menampilkan versi v5 non-arsip.

Untuk file schema v5 lengkap:

```bash
python manage.py import_obe_sample --path /path/ke/sample-data-2020-2026-obe-spec-v5.json
```

Batasi data mahasiswa ketika melakukan smoke test:

```bash
python manage.py import_obe_sample --path /path/ke/file.json --student-limit 10
```

File invalid, terpotong, schema selain `5.0.0`, atau jumlah katalog yang tidak sesuai akan ditolak sebelum transaksi database dimulai.

## Pemetaan ke model aplikasi

| Dataset v5 | Model aplikasi |
|---|---|
| program | `CurriculumVersion` |
| graduateProfiles, cpl, knowledgeAreas, cpmk | `Outcome` |
| courses | `Course` |
| hierarchy, cplToCpmk, course mappings | `CurriculumEdge` |
| course attainment | `AttainmentSnapshot` scope course/program |
| students | `StudentProfile` dan `AcademicStatus` |
| semesterRecords.irs | `EnrollmentPlan` |
| courseEnrollments | `AcademicResult` |
| academicRuleRegistry.rulePackages | `CohortRulePackage` |
| academicRuleRegistry.rules | `AcademicRule` |
| decision snapshot runtime | `AcademicDecision` |
| academicDecisions.overrides | workflow `DecisionOverride` tanpa perubahan data sumber |
| validationReport/runtime validator | `IntegrityValidationRun` dan `IntegrityIssue` |
| learning.rpsVersions | `CourseOffering` dan `RPSVersion` |
| learning.courseOutcomes/subOutcomes/indicators | `CourseOutcome`, `SubOutcome`, `PerformanceIndicator` |
| learning.weeklyPlans | `WeeklyPlan` |
| assessment.assessmentPlans | `AssessmentInstrument` dan `AssessmentItem` |
| assessment.rubricLibrary | `Rubric`, `RubricCriterion`, `PerformanceLevel` |

Credit policy v5 mencatat 129 SKS wajib dan `activationValid=false`. Importer mempertahankan fakta tersebut serta menempatkan kurikulum pada status `review`; gate aktivasi aplikasi tetap mensyaratkan tepat 126 SKS.

Status `published-demo` pada RPS/instrumen sumber hanya berlaku untuk fixture. Importer menyimpannya sebagai provenance dan membuat desain aplikasi sebagai `draft`; tidak ada approval institusi yang dipalsukan.
