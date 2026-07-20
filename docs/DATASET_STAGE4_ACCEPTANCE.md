# Acceptance Dataset OBE v5 Tahap 4

## Tujuan

Tahap 4 menutup seluruh kelompok rekonsiliasi yang sebelumnya masih `not_in_current_import_scope`. Sumber kanonik berada di `data/sample-data-2020-2026-obe-spec-v5.json` dengan ukuran 56.193.651 byte dan SHA-256:

```text
5d90915c2bbb46e9e44765299155c24782bccd2df75905c60c12e2391205aaa3
```

## Cakupan dan count

| Kelompok sumber | Count | Model aplikasi |
|---|---:|---|
| `evidence.manifests` | 366 | `FileManifest`, `EvidenceRecord` |
| `evidence.submissions` | 366 | `Submission` |
| `evidence.scoreRecords` | 366 | `Score` |
| `academicDecisions.overrides` | 3.330 | `AcademicDecision`, `DecisionOverride` |
| `featureFlags` | 10 | `FeatureFlag` |
| `auditTrail.events` | 7 | `AuditEvent` dengan hash sumber terpisah |
| `quality.issues` | 8 | `IntegrityIssue` |
| `quality.provusStandards` | 12 | `QualityStandard` |
| `quality.provusFindings` | 3 | `QualityFinding` |
| `quality.ppeppCycle` | 1 | `QualityCycle` |
| `ai.promptRegistry` | 4 | `PromptTemplate` |
| `secureExam.examDefinitions` | 1 | `Exam` |
| `academicLifecycle.applications` | 3 | `LifecycleApplication` |
| konfigurasi academic lifecycle | 1 | `LifecycleConfiguration` |
| `integration.contracts` | 5 | `IntegrationContract` |

## Pengamanan status demo

- `verified` pada manifest sumber disimpan sebagai `source_status`; evidence aplikasi tetap `submitted` karena file hanya memuat metadata/checksum, bukan byte artefak. Verifikasi resmi tetap memerlukan pemeriksaan content-addressed file.
- `approved-demo` pada override tidak menjadi approval resmi. Importer membuat decision `indeterminate` dan override `reviewed`; workflow institusi wajib melakukan replay maker-checker.
- Feature flag sumber disimpan sebagai provenance, tetapi runtime state tetap `disabled`.
- Secure Exam `approved-demo` disimpan sebagai exam `draft`. Paket hanya memuat metadata dan tidak berisi pertanyaan restricted.
- Prompt AI tetap `draft`; body prompt tidak dibuat-buat ketika sumber hanya memuat registry metadata.
- Hash audit sumber disimpan terpisah dari hash-chain aplikasi agar kedua rantai dapat diverifikasi tanpa mencampur skema canonicalization.

## Acceptance

Verifikasi file dan inventory cepat selalu dijalankan oleh suite:

```bash
pytest -q tests/test_sample_import.py -k repository_full
```

Acceptance database penuh menjalankan importer dua kali dan membandingkan laporan kedua dengan pertama:

```bash
OBE_FULL_SAMPLE_PATH="$PWD/data/sample-data-2020-2026-obe-spec-v5.json" \
  pytest -q tests/test_sample_import.py -k full_sample
```

Gate berhasil bila:

1. checksum dan ukuran file persis;
2. `source == imported` untuk seluruh kelompok Tahap 4;
3. tidak ada kelompok Tahap 4 pada `skipped`;
4. count database tepat dan putaran kedua identik;
5. 16.404 enrollment `planned` dan 12.118 `upcoming` tetap dilaporkan sebagai bukan hasil studi;
6. status demo tidak berubah menjadi official verified/approved/released/enabled.

Tahap 4 adalah penyelesaian impor dataset, bukan klaim bahwa seluruh spesifikasi produk PR-34–PR-88 sudah selesai. Status implementasi fitur tetap mengikuti `docs/TRACEABILITY.md`.
