# Implementation Plan: Excel Import

## Overview

This plan implements the Excel Import capability as a new Django app (`excel_import`) inside
the existing OBE modular monolith. It follows the generate → download → upload → stage →
dry-run → atomic-commit loop, building incrementally: data models and shared error
infrastructure first, then the versioned registry, deterministic generation, timeline
prefill, the upload safety pipeline, staging + dry-run, atomic commit, the facade and
lifecycle state machine, thin HTMX views, and finally end-to-end integration tests.

Every task integrates with owning modules (Curriculum, RPS, Attainment, Timeline) **only**
through their service layer, never their ORM models, and preserves the views ↔ service-layer
separation. Property-based tests (Hypothesis) reference the 23 correctness properties in the
design; example, edge-case, and integration tests round out coverage. Language/stack:
Python 3 / Django, `openpyxl` (pinned), `zipfile`, and Hypothesis.

## Tasks

- [x] 1. Scaffold `excel_import` app, data models, and shared error infrastructure
  - [x] 1.1 Create the `excel_import` Django app skeleton
    - Create the app package with `services/`, `definitions/`, and `migrations/` directories and register the app in Django settings
    - Add a `services/__init__.py` and empty module stubs (`facade.py`, `template_registry.py`, `template_generator.py`, `file_validator.py`, `staging.py`, `dry_run.py`, `commit_engine.py`, `scope_resolver.py`) so later tasks fill them in
    - Pin `openpyxl` and `hypothesis` in the project dependency manifest
    - _Requirements: 9.4, 9.5_

  - [x] 1.2 Implement `ImportBatch`, `StagedRow`, `TemplateDefinition` models
    - Define `ImportStatus` (Diunggah, Divalidasi, Ditolak, Dikomit, Digagalkan) and `RowClassification` (New/Changed/Unchanged/Duplicate/Rejected) text-choice enums
    - Implement `ImportBatch` reusing the shared `ProductionReadinessModel` base, with id, template_type, schema_version, Import_Scope fields (prodi/period/klass), timeline_task_id, status, content_hash
    - Implement `StagedRow` (batch FK, row_index, raw_values JSON, business_key, classification, cell_errors JSON, unique_together batch+row_index) and `TemplateDefinition` (append-only, unique_together template_type+schema_version, fields/reference_sources/validation_rules/business_key JSON)
    - _Requirements: 7.1, 7.2, 1.3, 1.4, 1.6, 5.4, 6.3, 9.1_

  - [x] 1.3 Generate initial migrations
    - Run `makemigrations` for the `excel_import` app and verify the migration applies cleanly
    - _Requirements: 9.4_

  - [x] 1.4 Implement `DomainError` hierarchy and plain-language message catalog
    - Implement `DomainError` dataclass with `problem`, `corrective_step`, `location`, and `to_message()`, plus subclasses (`DeferredTemplateError`, file-level validation errors, `SchemaVersionMismatchError`, `CommitFailedError`)
    - Create a `message_key`-keyed catalog of plain-language messages with no database/internal jargon
    - _Requirements: 8.1, 8.2, 8.3, 1.7, 5.7_

  - [x]* 1.5 Write property test for actionable, jargon-free messages
    - **Property 22: Messages are actionable** — every per-cell error and file-level rejection has a non-empty problem and corrective step
    - **Property 23: Messages are jargon-free** — no forbidden-token jargon appears in any message
    - **Validates: Requirements 8.1, 8.2, 8.3**

  - [x]* 1.6 Write unit tests for model constraints
    - Assert `status` is restricted to the five enum values and `StagedRow` classification uses the five allowed values; assert `ImportBatch` carries identity/scope/type/version
    - **Property 19: Batch creation carries identity and scope** / **Property 20: Status is always a valid state**
    - **Validates: Requirements 7.1, 7.2**

- [x] 2. Implement TemplateRegistry over versioned definitions
  - [x] 2.1 Seed declarative `TemplateDefinition`s and implement `TemplateRegistry`
    - Add declarative seed files in `definitions/` for all 8 types; mark Curriculum/CPL/RPS/Rubric implemented and Roster/Grades/Attainment_Measurement/CQI deferred; author full definitions (fields, reference sources, validation rules, business key, schema_version) for the 4 implemented types
    - Implement `list_types`, `is_implemented`, `get_current`, `get_version`, `implemented_types`, and `require_implemented` (raising `DeferredTemplateError` naming available types); load seeds append-only so a changed definition inserts a new version row and prior versions are retained
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7_

  - [x]* 2.2 Write property test for deferred-type rejection
    - **Property 1: Deferred types are always rejected with guidance** — for any deferred type and generate/import operation, the request is rejected with a message naming implemented types
    - **Validates: Requirements 1.7**

  - [x]* 2.3 Write property test for definition history and completeness
    - **Property 2: Definition history is preserved** — after any sequence of edits, every prior version is retrievable and count never decreases
    - **Property 3: Definitions are structurally complete and versioned** — each implemented current definition has non-empty fields, reference sources, rules, business key, and a well-formed schema version
    - **Validates: Requirements 1.3, 1.4, 1.5, 1.6**

  - [x]* 2.4 Write example tests for registry contents
    - Assert exactly 8 registered types with the correct implemented/deferred split; deferred-type request returns the not-available message listing available types
    - _Requirements: 1.1, 1.2, 1.7_

- [x] 3. Implement deterministic TemplateGenerator
  - [x] 3.1 Build the five fixed-order sheets and embedded identity
    - Implement `generate(definition, scope, reference_rows, prefill_rows)` producing sheets in fixed order Petunjuk, Metadata, Data, Referensi, Validasi; populate Validasi from the definition's validation rules
    - Embed Template_Id and Schema_Version into Metadata named cells and `docProps/custom` custom properties; write every cell as a literal value and never emit a value formula
    - _Requirements: 2.1, 2.2, 2.3, 2.5_

  - [x] 3.2 Implement byte-stable output normalization
    - Sort data rows by business key and reference rows by stable key, apply fixed styles and constant document metadata (FIXED_EPOCH created/modified), and implement `normalize_xlsx_zip` to re-pack OOXML parts with fixed member order, timestamps, and compression
    - _Requirements: 2.4_

  - [x]* 3.3 Write property test for generation determinism
    - **Property 4: Generation determinism** — generating twice from identical inputs yields byte-identical output
    - **Validates: Requirements 2.4**

  - [x]* 3.4 Write property test for workbook structure and formula-freedom
    - **Property 5: Generated workbook structure** — exactly the five named sheets, Validasi contains every validation rule
    - **Property 7: Generated workbooks contain no value formulas** — no cell is a value formula
    - **Validates: Requirements 2.1, 2.3, 2.5**

  - [x]* 3.5 Write property test for embedded identity round-trip
    - **Property 6: Embedded identity round-trip** — reading back embedded identity yields the source definition's Template_Id and Schema_Version
    - **Validates: Requirements 2.2**

- [x] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement ScopeResolver and prefill via service layer
  - [x] 5.1 Implement `ScopeResolver` resolve/reference/prior-data methods
    - Implement `resolve` using `TimelineService.get_task` to derive Import_Scope (prodi/period/klass) and enforce template-type consistency with the task's associated type
    - Implement `reference_data` (each definition reference source names a peer service + method, read via the service layer) and `prior_data` (prior editable records via the owning service); wire results into the generator's Referensi and Data sheets
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 9.1_

  - [x]* 5.2 Write property test for timeline scope prefill
    - **Property 8: Timeline scope prefill** — Metadata records prodi/period/class resolved from the task via the service layer and the recorded type equals the task's type
    - **Validates: Requirements 3.1, 3.4**

  - [x]* 5.3 Write property test for reference and prior-data prefill
    - **Property 9: Reference and prior-data prefill** — Referensi equals the service-provided reference dataset and Data is prefilled with exactly the service-provided prior data
    - **Validates: Requirements 3.2, 3.3**

- [x] 6. Implement FileValidator safety pipeline
  - [x] 6.1 Implement the ordered upload safety pipeline
    - Implement `validate_file(file_bytes, declared_mime)` running ordered checks: `.xlsx` extension + OOXML magic, MIME match, max size, valid OOXML zip, zip-bomb guard (decompressed size + ratio via `zipfile`), macro detection (`vbaProject.bin`/xlsm), encryption/password (OLE CFB / EncryptedPackage), external links / embedded objects, and a value-formula scan; raise file-level `DomainError`s and never parse business content until all checks pass
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8_

  - [x]* 6.2 Write property test for unsafe-upload rejection
    - **Property 10: Unsafe uploads are rejected** — for every family of unsafe file, the validator rejects with an explaining message and no business parsing occurs
    - **Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8**

  - [x]* 6.3 Write edge-case tests for size boundary and malformed content
    - At-limit size passes the size stage and one byte over is rejected; renamed non-xlsx, empty, and OLE-encrypted fixtures are rejected with actionable messages
    - _Requirements: 4.1, 4.3, 4.6_

- [x] 7. Implement StagingArea and DryRunValidator
  - [x] 7.1 Implement `StagingArea` parse-and-persist
    - Parse the Data sheet into `ParsedRow`s and persist them as `StagedRow`s under a new `ImportBatch` (status Diunggah) before any owning-module write; implement `stage` and `rows`
    - _Requirements: 5.1_

  - [x] 7.2 Implement `DryRunValidator` classification and reporting
    - Select the definition via embedded Template_Id + Schema_Version, rejecting on version mismatch; validate each row's cells against rules, detect intra-batch business-key duplicates, and assign exactly one classification (New/Changed/Unchanged/Duplicate/Rejected) using a read-only service snapshot; produce a `DryRunReport` with one entry per row and persist classifications without any target write
    - _Requirements: 5.2, 5.3, 5.4, 5.5, 5.6, 5.7_

  - [x]* 7.3 Write property test for dry-run no-writes
    - **Property 11: Dry-run performs no target writes** — staging and dry-run persist rows and produce a report with no owning-module write
    - **Validates: Requirements 5.1, 5.6**

  - [x]* 7.4 Write property test for validate-and-classify-once and duplicates
    - **Property 12: Every staged row is validated and classified exactly once** — one classification and one report entry per row
    - **Property 13: Intra-batch duplicate detection** — rows sharing a business key within a batch are Duplicate_Row
    - **Validates: Requirements 5.2, 5.3, 5.4, 5.5**

  - [x]* 7.5 Write property test for schema-version mismatch rejection
    - **Property 14: Schema-version mismatch is rejected** — an embedded version with no matching definition rejects the batch with a mismatch message
    - **Validates: Requirements 5.7**

- [x] 8. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Implement CommitEngine (atomic, idempotent)
  - [x] 9.1 Implement single-transaction, business-key upsert commit
    - Implement `commit(batch)` wrapping all committable rows in one `transaction.atomic()`, excluding Rejected_Row and skipping Unchanged_Row; upsert each row by business key via the owning service, record Production_Readiness_Fields through the service, and produce a `ReconciliationSummary` (inserted/updated/skipped/rejected)
    - On any write failure, roll back all writes leaving owning modules unchanged and persist the failed status in a separate transaction; use `content_hash` to recognize identical re-uploads
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7_

  - [x]* 9.2 Write property test for commit atomicity
    - **Property 15: Commit atomicity** — a write failure at any row rolls back the entire batch and leaves owning services identical to the pre-commit snapshot
    - **Validates: Requirements 6.1, 6.2**

  - [x]* 9.3 Write property test for idempotent upsert
    - **Property 16: Idempotent business-key upsert** — committing once and twice yield the same target-service state, one record per business key
    - **Validates: Requirements 6.3, 6.4**

  - [x]* 9.4 Write property test for reconciliation conservation and readiness fields
    - **Property 17: Reconciliation summary conservation** — inserted+updated+skipped+rejected sum to the staged-row total, match each row's outcome, and no Rejected_Row is written
    - **Property 18: Committed records carry production-readiness fields** — every written record records all readiness fields through the service layer
    - **Validates: Requirements 6.5, 6.6, 6.7**

- [x] 10. Implement ExcelImportService facade and lifecycle state machine
  - [x] 10.1 Implement the transport-agnostic facade and status transitions
    - Implement `ExcelImportService` composing registry, generator, scope resolver, file validator, staging, dry-run, and commit engine; expose `generate_workbook`, `upload_and_dry_run`, `commit`, `get_batch`, `get_report` accepting/returning plain bytes/ids/DTOs (no HttpRequest/HttpResponse)
    - Own the five-status lifecycle: create Diunggah on upload, set Divalidasi on passing dry-run, Ditolak on file/dry-run rejection, Dikomit on successful commit, Digagalkan on rollback; keep the full loop synchronous with no worker/broker
    - _Requirements: 7.3, 7.4, 7.5, 7.6, 7.7, 9.2_

  - [x]* 10.2 Write property test for lifecycle transition and status validity
    - **Property 21: Lifecycle transition correctness** — passing dry-run → Divalidasi, rejection → Ditolak, successful commit → Dikomit, rollback → Digagalkan
    - **Property 20: Status is always a valid state** — status stays within the five allowed values across any operation sequence
    - **Validates: Requirements 7.2, 7.3, 7.4, 7.5, 7.6**

- [x] 11. Implement thin HTMX views and URL wiring
  - [x] 11.1 Implement generate/download, upload+dry-run, and commit views
    - Implement thin HTMX request handlers that delegate to the facade: generate + stream the `.xlsx` download, upload → render the dry-run report, confirm → render the reconciliation summary; keep all business logic in the service layer and wire the app URLs
    - _Requirements: 9.2, 7.7_

- [x] 12. Integration, boundary, and smoke tests
  - [x]* 12.1 Write end-to-end single-request loop test
    - Drive generate → upload → dry-run → commit within one request, asserting a single transaction boundary and in-request completion with no broker/worker
    - _Requirements: 6.1, 7.7, 9.5_

  - [x]* 12.2 Write service-layer boundary and migration-drift tests
    - Assert `excel_import` imports peer *services* only and never peer `models`, that services carry no request/response dependency, and run `makemigrations --check` for migration drift
    - _Requirements: 9.1, 9.2, 9.4_

- [x] 13. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional test tasks and can be skipped for a faster MVP; core implementation tasks are never optional.
- Each task references the specific requirements and/or design correctness properties it implements for full traceability.
- The design has a "Correctness Properties" section, so Hypothesis property-based tests (tagged `Feature: excel-import, Property {n}`) are included and placed close to the implementation they validate to catch errors early; example, edge-case, and integration tests complement them.
- All owning-module access (Curriculum, RPS, Attainment, Timeline) goes exclusively through the service layer — never their ORM models — and views stay thin so a future JSON API can reuse the facade unchanged.
- Checkpoints ensure incremental validation at reasonable breaks.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "1.4"] },
    { "id": 2, "tasks": ["1.3", "1.5", "1.6", "2.1"] },
    { "id": 3, "tasks": ["2.2", "2.3", "2.4", "3.1", "6.1"] },
    { "id": 4, "tasks": ["3.2", "3.5", "5.1", "6.2", "6.3"] },
    { "id": 5, "tasks": ["3.3", "3.4", "5.2", "5.3", "7.1"] },
    { "id": 6, "tasks": ["7.2", "9.1"] },
    { "id": 7, "tasks": ["7.3", "7.4", "7.5", "9.2", "9.3", "9.4"] },
    { "id": 8, "tasks": ["10.1"] },
    { "id": 9, "tasks": ["10.2", "11.1"] },
    { "id": 10, "tasks": ["12.1", "12.2"] }
  ]
}
```
