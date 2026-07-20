# Dataset Sintetis OBE v5

## Import bawaan

`fixtures/sample-data-2020-2026-obe-spec-v5.compact.json` memuat katalog lengkap schema v5: 5 PL, 12 CPL, 18 bahan kajian, 31 CPMK, 77 mata kuliah, seluruh pemetaan, agregat capaian mata kuliah, serta empat riwayat mahasiswa sintetis representatif. Untuk bagian master/governance dan learning/assessment yang tidak disalin ke fixture compact, importer memakai irisan kanonik file v5 lengkap: 2 versi kurikulum, 2 package cohort, 11 academic rule, dan RPS `MIK1624101` beserta outcome, 16 minggu, enam instrumen, dan dua rubrik.

File lengkap juga tersedia di `data/sample-data-2020-2026-obe-spec-v5.json`. Tahap 4 mengimpor registry evidence, submission/score, override demo, feature flag, audit sumber, quality/Provus/PPEPP, prompt AI, Secure Exam, lifecycle, dan kontrak integrasi. Rincian count dan gate terdapat di [Acceptance Tahap 4](DATASET_STAGE4_ACCEPTANCE.md).

File v5 lengkap dapat diberikan melalui `--path`; master kurikulum, package, rule, dosen, penugasan, alias, seluruh course offering, desain RPS, rubrik, dan assessment plan dari file tersebut menjadi sumber utama. Fallback kanonik hanya dipakai untuk fixture compact dan mempunyai nilai yang sama dengan `curriculumVersions` serta `academicRuleRegistry` v5.

## Menjalankan import

```bash
python manage.py import_obe_sample
```

Importer bersifat transaksional dan idempotent. Menjalankannya kembali memperbarui record dengan identifier yang sama tanpa menggandakan data.

Jika volume lokal masih memuat seed generik lama (`program_code=IF` tanpa provenance), importer menandainya `archived`. Record tidak dihapus, tetapi katalog pengguna hanya menampilkan versi v5 non-arsip.

Untuk file schema v5 lengkap:

```bash
python manage.py import_obe_sample \
  --path /path/ke/sample-data-2020-2026-obe-spec-v5.json \
  --report var/import-reconciliation-v5.json
```

Laporan rekonsiliasi berisi checksum sumber serta kelompok `source`, `imported`,
`skipped`, dan `errors`. Gunakan laporan ini sebagai bukti bahwa volume sumber
sesuai dengan hasil import. Bagian dataset yang belum menjadi cakupan importer
ditandai `not_in_current_import_scope`, sehingga tidak dapat keliru dianggap
sudah tersimpan. Untuk file v5 lengkap saat ini, 56.119 enrollment
`completed` menjadi `AcademicResult`; 16.404 `planned` dan 12.118 `upcoming`
tetap tercatat pada `EnrollmentPlan` dan dilaporkan sebagai hasil yang dilewati.
Enrollment yang belum selesai tidak boleh diberi nilai nol atau nilai huruf semu.

Batasi data mahasiswa ketika melakukan smoke test:

```bash
python manage.py import_obe_sample --path /path/ke/file.json --student-limit 10
```

File invalid, terpotong, schema selain `5.0.0`, jumlah katalog yang tidak sesuai,
referensi kurikulum/package/dosen yang yatim, skala nilai yang tidak konsisten,
status enrollment yang tidak dikenal, atau enrollment `completed` tanpa nilai
akan ditolak sebelum transaksi database dimulai.

## Pemetaan ke model aplikasi

| Dataset v5 | Model aplikasi |
|---|---|
| curriculumVersions | `CurriculumVersion` dengan UUID/checksum sumber |
| graduateProfiles, cpl, knowledgeAreas, cpmk | `Outcome` |
| courses | `Course` |
| hierarchy, cplToCpmk, course mappings | `CurriculumEdge` |
| course attainment | `AttainmentSnapshot` scope course/program |
| students | `StudentProfile` dan `AcademicStatus` |
| semesterRecords.irs | `EnrollmentPlan` |
| courseEnrollments berstatus `completed` | `AcademicResult` |
| courseEnrollments `planned`/`upcoming` | Tetap pada `EnrollmentPlan`; bukan hasil studi |
| academicRuleRegistry.rulePackages | `CohortRulePackage` |
| gradeScaleLegacy, gradeScaleCurrent | `CohortRulePackage.grade_scheme` |
| academicRuleRegistry.rules | `AcademicRule` |
| lecturers, lecturerWorkloadSummary | `LecturerProfile` |
| identity.scopedAssignments | `RoleAssignment` berscope DPA/koordinator |
| identifierAliases.courseCodes/courseOfferings | `IdentifierAlias` |
| decision snapshot runtime | `AcademicDecision` |
| academicDecisions.overrides | workflow `DecisionOverride` tanpa perubahan data sumber |
| validationReport/runtime validator | `IntegrityValidationRun` dan `IntegrityIssue` |
| courseOfferings | `CourseOffering` dengan `source_id`, parallel group, dosen, jadwal, ruang, dan provenance |
| learning.rpsVersions | `RPSVersion` dengan `source_id` dan provenance checksum |
| learning.courseOutcomes/subOutcomes/indicators | `CourseOutcome`, `SubOutcome`, `PerformanceIndicator` |
| learning.weeklyPlans | `WeeklyPlan` |
| assessment.assessmentPlans | `AssessmentInstrument` dan `AssessmentItem` |
| assessment.rubricLibrary | `Rubric`, `RubricCriterion`, `PerformanceLevel` |
| evidence.manifests/submissions/scoreRecords | `FileManifest`, `EvidenceRecord`, `Submission`, `Score` |
| academicDecisions.overrides | `AcademicDecision` + `DecisionOverride` dengan provenance demo |
| featureFlags | `FeatureFlag` dalam runtime state aman `disabled` |
| auditTrail.events | `AuditEvent` dengan source hash terpisah |
| quality.issues/provusStandards/provusFindings/ppeppCycle | `IntegrityIssue`, `QualityStandard`, `QualityFinding`, `QualityCycle` |
| ai.promptRegistry | `PromptTemplate` draft metadata-only |
| secureExam | `Exam` draft beserta metadata edge/package/session/go-no-go |
| academicLifecycle | `LifecycleConfiguration`, `LifecycleApplication` |
| integration.contracts | `IntegrationContract` |

Credit policy v5 mencatat 129 SKS wajib dan `activationValid=false`. Importer mempertahankan fakta tersebut serta menempatkan kurikulum pada status `review`; gate aktivasi aplikasi tetap mensyaratkan tepat 126 SKS.

Referensi mahasiswa tidak lagi disimpan sebagai UUID turunan. Cohort 2020–2023
menunjuk UUID `CURR-LEGACY-DEMO-V1`, cohort 2024+ menunjuk UUID
`CURR-S1IF-2024-V1`, dan package disimpan terpisah sebagai `code` + `version`.
Dengan demikian query kurikulum dan aturan tidak mempunyai referensi yatim.

Status `published-demo` pada RPS/instrumen sumber hanya berlaku untuk fixture. Importer menyimpannya sebagai provenance dan membuat desain aplikasi sebagai `draft`; tidak ada approval institusi yang dipalsukan.

## Acceptance file penuh

Acceptance lokal atau staging harus memakai file penuh tanpa `--student-limit`:

```bash
OBE_FULL_SAMPLE_PATH="$PWD/data/sample-data-2020-2026-obe-spec-v5.json" \
  pytest tests/test_sample_import.py -k full_sample
```

Tes menjalankan import dua kali dan memverifikasi dua kurikulum kanonik, 12 baris
skala nilai, 43 dosen, 36 penugasan, 3.851 alias identifier, 3.850 offering,
77 RPS, 1.232 minggu, 459 assessment plan, 1.597 mahasiswa, 12.776 enrollment
plan, 56.119 hasil studi selesai, rekonsiliasi 84.641 enrollment, serta
idempotensi seluruh count. Acceptance Tahap 4 juga memverifikasi 366 manifest,
366 submission, 366 score, 3.330 override, 10 feature flag, 7 audit event,
8 quality issue, 12 standard, 3 finding, 4 prompt, 1 Secure Exam, 3 lifecycle
application, dan 5 integration contract. `--student-limit 0` hanya valid
untuk smoke test domain non-mahasiswa dan tidak boleh dipakai sebagai bukti
acceptance file penuh.
