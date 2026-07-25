# Requirements Document

## Introduction

This document specifies the Minimum Viable Product (MVP) for the Excel Import capability of the Outcome-Based Education (OBE) management system. The capability provides a complete, safe, and reproducible bulk-authoring loop for structural authoring templates: a user generates a typed Excel workbook from a versioned template registry, downloads it pre-filled with the scope and reference data of a timeline Task, edits it offline, uploads it, receives a dry-run report of exactly what will change before anything is written, and then commits the batch as a single all-or-nothing transaction whose keyed upserts make re-uploads idempotent.

The MVP implements the full generate to download to upload to staging to dry-run to atomic-commit loop end-to-end for four structural authoring template types: Curriculum, CPL, RPS, and Rubric. Four further template types (Roster, Grades, Attainment-Measurement, and CQI) are registered in the catalog as deferred so that they can be added later without restructuring, but their import behavior is out of scope for this MVP.

Import runs synchronously within the request cycle: an upload is parsed, validated as a dry-run, and committed inside a single interaction, with no background worker, message broker, or additional container. An import is tracked as a batch record that carries an identifier and a status, and retrying an import by re-uploading is idempotent. Real-time asynchronous progress reporting and mid-run cancellation are out of scope for this MVP.

The capability is built as part of the existing Django and PostgreSQL modular monolith. It integrates with the existing OBE module services (Curriculum, RPS, Attainment, and Timeline) only through their service layer and never accesses their persistence models directly. The design must not preclude later addition of a JSON API over the same service layer, additional template types, or asynchronous execution.

## Glossary

- **Excel_Import_System**: The complete Excel import and generation capability described in this document.
- **Template_Registry**: The versioned catalog subsystem that defines each Template_Type together with its fields, reference data, and validation rules.
- **Template_Type**: A named category of authoring workbook. The implemented types are Curriculum, CPL, RPS, and Rubric. The deferred types are Roster, Grades, Attainment_Measurement, and CQI.
- **Implemented_Template_Type**: A Template_Type whose full import loop is delivered in this MVP: Curriculum, CPL, RPS, or Rubric.
- **Deferred_Template_Type**: A Template_Type that is registered in the Template_Registry but whose import loop is out of scope for this MVP: Roster, Grades, Attainment_Measurement, or CQI.
- **Template_Definition**: The versioned configuration record for a Template_Type that specifies its fields, reference data sources, and validation rules.
- **Template_Generator**: The subsystem that produces an Excel workbook from a Template_Definition.
- **Workbook**: A single `.xlsx` file produced by the Template_Generator or uploaded by a user.
- **Instruction_Sheet**: The workbook sheet named Petunjuk that explains how to complete the workbook.
- **Metadata_Sheet**: The workbook sheet named Metadata that carries scope and identity fields.
- **Data_Sheet**: The workbook sheet named Data that holds the editable rows to be imported.
- **Reference_Sheet**: The workbook sheet named Referensi that holds read-only reference data.
- **Validation_Sheet**: The workbook sheet named Validasi that documents the validation rules applied to the Data_Sheet.
- **Template_Id**: The identifier of the Template_Type embedded in a generated Workbook.
- **Schema_Version**: The version of the Template_Definition embedded in a generated Workbook.
- **Timeline_Task**: A Task in the Timeline_Engine of the OBE system, as defined in the OBE system requirements, from which a Workbook is generated and to which an import is scoped.
- **Import_Scope**: The combination of program of study (prodi), academic period, and class that bounds a Workbook and its import.
- **Import_Batch**: The tracked record of one import, carrying an identifier, an Import_Scope, a Template_Type, a Schema_Version, and an Import_Status.
- **Import_Status**: The lifecycle state of an Import_Batch, one of: Diunggah (uploaded), Divalidasi (validated), Ditolak (rejected), Dikomit (committed), Digagalkan (failed).
- **Staging_Area**: The subsystem that stores the parsed rows of an uploaded Workbook before any commit.
- **Dry_Run_Validator**: The subsystem that validates staged rows and produces a Dry_Run_Report without writing to the target module services.
- **Dry_Run_Report**: The per-batch report that classifies each staged row as new, changed, unchanged, duplicate, or rejected, and lists per-cell errors.
- **Row_Classification**: The outcome assigned to a staged row: New_Row, Changed_Row, Unchanged_Row, Duplicate_Row, or Rejected_Row.
- **Business_Key**: The set of fields of a Template_Type that uniquely identifies a target record and drives idempotent upserts.
- **Commit_Engine**: The subsystem that writes a validated Import_Batch to the target module services within a single database transaction.
- **Reconciliation_Summary**: The per-batch tally of inserted, updated, skipped, and rejected rows produced by the Commit_Engine.
- **File_Validator**: The subsystem that checks an uploaded file for safety and format before parsing.
- **Value_Formula**: An Excel formula stored in a worksheet cell that computes a value.
- **Zip_Bomb**: A compressed file crafted to expand to a disproportionately large size when decompressed.
- **Production_Readiness_Fields**: The metadata set stored on every entity: program of study (prodi), owner, status, version, creator, created-time, and modified-time.
- **Service_Layer**: The interface through which the Excel_Import_System reads from and writes to the Curriculum, RPS, Attainment, and Timeline modules without accessing their persistence models directly.

## Requirements

### Requirement 1: Versioned Template Catalog and Registry

**User Story:** As a Kaprodi, I want a versioned registry of Excel template types with their fields, reference data, and validation rules, so that every workbook is generated and validated from one authoritative and evolvable source.

#### Acceptance Criteria

1. THE Template_Registry SHALL register the Template_Types Curriculum, CPL, RPS, Rubric, Roster, Grades, Attainment_Measurement, and CQI.
2. THE Template_Registry SHALL mark Curriculum, CPL, RPS, and Rubric as Implemented_Template_Type and SHALL mark Roster, Grades, Attainment_Measurement, and CQI as Deferred_Template_Type.
3. THE Template_Registry SHALL store, for each Template_Type, a Template_Definition that specifies the fields, the reference data sources, and the validation rules of that Template_Type.
4. THE Template_Registry SHALL assign a Schema_Version to each Template_Definition.
5. WHEN a Template_Definition is changed, THE Template_Registry SHALL retain the prior Template_Definition version as a historical record rather than overwriting it.
6. THE Template_Registry SHALL store each Template_Definition as a versioned configuration record.
7. IF a request references a Deferred_Template_Type for generation or import, THEN THE Excel_Import_System SHALL reject the request and return a message that states the Template_Type is not yet available and identifies the available Template_Types.

### Requirement 2: Deterministic Excel Workbook Generation

**User Story:** As a Lecturer, I want the system to generate a structured workbook that always looks the same for the same inputs, so that authoring is predictable and generated files can be compared reliably.

#### Acceptance Criteria

1. WHEN a user requests a Workbook for an Implemented_Template_Type, THE Template_Generator SHALL produce a `.xlsx` Workbook containing the sheets Petunjuk, Metadata, Data, Referensi, and Validasi.
2. THE Template_Generator SHALL embed the Template_Id and the Schema_Version of the source Template_Definition into each generated Workbook.
3. WHEN the Template_Generator produces a Workbook, THE Template_Generator SHALL populate the Validation_Sheet with the validation rules defined for the Template_Type in the Template_Definition.
4. WHEN the Template_Generator is invoked more than once with identical inputs, THE Template_Generator SHALL produce byte-identical Workbook output.
5. THE Template_Generator SHALL exclude Value_Formulas from every generated Workbook.

### Requirement 3: Template-to-Timeline-Task Linking and Prefill

**User Story:** As a Lecturer, I want to download a template directly for a timeline task pre-filled with my program, period, class, reference data, and prior edits, so that I start from my real context instead of a blank sheet.

#### Acceptance Criteria

1. WHEN a user requests a Workbook for a Timeline_Task, THE Excel_Import_System SHALL resolve the Import_Scope from the Timeline_Task through the Service_Layer and SHALL write the program of study, academic period, and class into the Metadata_Sheet.
2. WHEN the Template_Generator produces a Workbook for a Timeline_Task, THE Template_Generator SHALL populate the Reference_Sheet with the reference data defined for the Template_Type in the Template_Definition, read through the Service_Layer.
3. WHERE prior editable data exists for the Import_Scope of the Timeline_Task, THE Template_Generator SHALL pre-fill the Data_Sheet with that prior data read through the Service_Layer.
4. THE Excel_Import_System SHALL record the Template_Type of a Timeline_Task-linked Workbook consistently with the Template_Type associated with that Timeline_Task.

### Requirement 4: Safe Workbook Upload Validation

**User Story:** As a Kaprodi, I want uploaded files checked for unsafe content and format before they are parsed, so that malicious or malformed files cannot compromise the system.

#### Acceptance Criteria

1. WHEN a file is uploaded, THE File_Validator SHALL accept the file only if the file is in `.xlsx` format and SHALL reject any other format.
2. WHEN a file is uploaded, THE File_Validator SHALL verify that the declared MIME type of the file matches the `.xlsx` format.
3. IF an uploaded file exceeds the configured maximum file size, THEN THE File_Validator SHALL reject the file and return a message that states the size limit and the corrective step.
4. IF an uploaded file expands beyond the configured decompressed-size limit or decompression-ratio limit, THEN THE File_Validator SHALL reject the file as a suspected Zip_Bomb and return a message that states the problem and the corrective step.
5. IF an uploaded file contains macros, THEN THE File_Validator SHALL reject the file and return a message identifying the macro content and the corrective step.
6. IF an uploaded file is password protected, THEN THE File_Validator SHALL reject the file and return a message stating that password-protected files are not accepted and the corrective step.
7. IF an uploaded file contains external links, embedded files, or embedded objects, THEN THE File_Validator SHALL reject the file and return a message identifying the unsafe content and the corrective step.
8. IF an uploaded file contains a Value_Formula in any cell, THEN THE File_Validator SHALL reject the file and return a message identifying the formula location and the corrective step.

### Requirement 5: Staging and Dry-Run Reporting

**User Story:** As a Lecturer, I want every upload to be staged and reported as a dry run before anything is saved, so that I can see and correct exactly what will change before I commit.

#### Acceptance Criteria

1. WHEN a Workbook passes File_Validator checks, THE Staging_Area SHALL store the parsed rows of the Data_Sheet before any write to the target module services occurs.
2. WHEN rows are staged, THE Dry_Run_Validator SHALL validate each staged row against the validation rules of the Template_Definition identified by the embedded Template_Id and Schema_Version.
3. WHEN validation completes, THE Dry_Run_Validator SHALL assign each staged row a Row_Classification of New_Row, Changed_Row, Unchanged_Row, Duplicate_Row, or Rejected_Row.
4. THE Dry_Run_Validator SHALL classify a staged row as Duplicate_Row WHEN more than one staged row shares the same Business_Key within the Import_Batch.
5. THE Dry_Run_Validator SHALL produce a Dry_Run_Report that lists, for each staged row, the Row_Classification and any per-cell errors.
6. WHILE an Import_Batch has not been committed, THE Dry_Run_Validator SHALL NOT write any staged row to the target module services.
7. IF the embedded Schema_Version of an uploaded Workbook does not match a Template_Definition version in the Template_Registry, THEN THE Dry_Run_Validator SHALL reject the Import_Batch and return a message identifying the version mismatch and the corrective step.

### Requirement 6: Atomic and Idempotent Commit

**User Story:** As a Kaprodi, I want a validated batch committed all-or-nothing with keyed upserts, so that partial writes never occur and re-uploading the same file never creates duplicates.

#### Acceptance Criteria

1. WHEN a user commits a validated Import_Batch, THE Commit_Engine SHALL write all committable rows of the Import_Batch within a single database transaction through the Service_Layer.
2. IF any write in the transaction fails, THEN THE Commit_Engine SHALL roll back the entire Import_Batch and SHALL leave the target module services unchanged.
3. WHEN the Commit_Engine writes a row, THE Commit_Engine SHALL upsert the target record by its Business_Key so that a row matching an existing record updates that record rather than inserting a duplicate.
4. WHEN the same Workbook is uploaded and committed more than once, THE Commit_Engine SHALL leave the target module services in a state identical to a single commit.
5. WHEN a commit completes, THE Commit_Engine SHALL produce a Reconciliation_Summary that reports the counts of inserted, updated, skipped, and rejected rows for the Import_Batch.
6. THE Commit_Engine SHALL exclude every Rejected_Row from the commit.
7. WHEN the Commit_Engine writes a target record, THE Commit_Engine SHALL record the Production_Readiness_Fields for that record through the Service_Layer.

### Requirement 7: Tracked Synchronous Import Batch

**User Story:** As a Kaprodi, I want each import tracked as a batch record with an identifier and status executed within the request, so that I can see the outcome of each import and safely retry by re-uploading.

#### Acceptance Criteria

1. WHEN a Workbook is uploaded, THE Excel_Import_System SHALL create an Import_Batch that carries an identifier, the Import_Scope, the Template_Type, and the Schema_Version.
2. THE Excel_Import_System SHALL restrict each Import_Status to one of: Diunggah, Divalidasi, Ditolak, Dikomit, Digagalkan.
3. WHEN the Dry_Run_Validator completes without rejecting the Import_Batch, THE Excel_Import_System SHALL set the Import_Status to Divalidasi.
4. WHEN the File_Validator or the Dry_Run_Validator rejects an Import_Batch, THE Excel_Import_System SHALL set the Import_Status to Ditolak.
5. WHEN the Commit_Engine completes a commit successfully, THE Excel_Import_System SHALL set the Import_Status to Dikomit.
6. IF a commit is rolled back, THEN THE Excel_Import_System SHALL set the Import_Status to Digagalkan.
7. THE Excel_Import_System SHALL parse, validate, and commit an Import_Batch within a single synchronous request cycle without a background worker or message broker.

### Requirement 8: Explainable Validation Messages

**User Story:** As a Lecturer, I want every error to explain the problem and how to fix it in plain language, so that I can correct my workbook without technical support.

#### Acceptance Criteria

1. WHEN the Excel_Import_System reports a per-cell error, THE Excel_Import_System SHALL state the problem and the corrective step for that cell.
2. WHEN the Excel_Import_System reports a file-level rejection, THE Excel_Import_System SHALL state the problem and the corrective step for the file.
3. THE Excel_Import_System SHALL express validation messages in plain language without database or internal system terminology.

### Requirement 9: Module Integration and Architecture Constraints

**User Story:** As a Dev Administrator, I want the import capability to integrate through service layers and managed schema, so that it stays decoupled from module internals and evolves predictably.

#### Acceptance Criteria

1. THE Excel_Import_System SHALL read from and write to the Curriculum, RPS, Attainment, and Timeline modules only through the Service_Layer and SHALL NOT access those modules' persistence models directly.
2. THE Excel_Import_System SHALL separate request-handling views from the Service_Layer so that a JSON API can reuse the Service_Layer without change.
3. THE Excel_Import_System SHALL compose all database statements through the framework data-access layer using parameterized queries rather than string-concatenated SQL.
4. THE Excel_Import_System SHALL apply all database schema changes through Django migrations.
5. WHEN a Dev Administrator starts the OBE system with the existing web container and database container, THE Excel_Import_System SHALL operate without requiring an additional container.
