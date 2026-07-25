# Implementation Plan: OBE System (MVP Vertical Loop)

## Overview

This plan implements the OBE_System as a Django + PostgreSQL modular monolith, built bottom-up along one complete vertical loop. It starts with project scaffolding, Docker Compose, and the shared/core foundation, then layers the five business modules (Timeline_Engine, Curriculum_Module, RPS_Module, Attainment_Engine), the Data_Injection_Tool, and finally the five UI workspaces.

Every task respects the strict **views ↔ service-layer separation** (Requirement 18.4): views parse input and call exactly one service method; all business logic and validation lives in the service layer and raises `DomainError`. Cross-module collaboration always goes through service interfaces, never through another module's ORM models.

Property-based tests use **Hypothesis** (min. 100 iterations, tagged `Feature: obe-system, Property {n}: {text}`) and reference the 27 correctness properties from the design. Example, edge-case, integration, and smoke tests follow the design's testing strategy. All test sub-tasks are optional (marked `*`).

## Tasks

- [ ] 1. Project scaffolding, Docker Compose, and shared/core foundation
  - [x] 1.1 Scaffold Django project, apps, settings, and Docker Compose
    - Create the Django 5.x project with focused apps: `core`, `timeline`, `curriculum`, `rps`, `attainment`, `injection`, `web` (presentation)
    - Configure PostgreSQL 16 settings, `requirements.txt` (Django, psycopg, HTMX helpers, Hypothesis, pytest-django)
    - Add `Dockerfile` and `docker-compose.yml` defining a `web` container (Django) and a `db` container (PostgreSQL) startable via `docker compose up -d --build`
    - Establish the views/service-layer package convention (each module has `models.py`, `services.py`, `validators.py`, `dtos.py`)
    - _Requirements: 18.1, 18.3, 18.4_

  - [x] 1.2 Implement the shared ProductionReadinessModel base and core entities
    - Implement abstract `ProductionReadinessModel` (prodi, owner, status, version, creator, created_time, modified_time)
    - Implement `ProgramOfStudy`, `DemoUser` (role, no real auth), `ConfigRecord` (versioned rules/standards/formulas), `DataInjectionLog`
    - Create migrations for all core models
    - _Requirements: 1.3, 6.3, 8.4, 9.4, 18.2_

  - [x] 1.3 Implement DomainError and explainable validation utilities
    - Implement `DomainError(message, corrective_step)` exception
    - Implement shared validation utilities that format plain-language messages (problem + corrective step) and a jargon blocklist helper (no "foreign key", "constraint", "null", table names)
    - _Requirements: 14.2, 14.3_

  - [x] 1.4 Implement Role_Switcher context and Dev_Banner
    - Implement in-app role/session context that swaps the active `DemoUser`/role without authentication, isolated so real auth can later replace it
    - Render a persistent `Dev_Banner` in the base template stating the environment is development with synthetic data
    - Ensure the app operates without real authentication, SSO, or permission enforcement
    - _Requirements: 15.2, 15.3, 15.4, 18.4_

  - [x]* 1.5 Write property test for validation messages
    - **Property 25: Validation messages are plain-language and actionable**
    - **Validates: Requirements 14.2, 14.3**

  - [x]* 1.6 Write unit tests for core foundation
    - Test role switch changes available actions (15.2), Dev_Banner presence (15.3), and versioned ConfigRecord behavior (18.2)
    - _Requirements: 15.2, 15.3, 18.2_

- [ ] 2. Implement Timeline_Engine models and instantiation
  - [ ] 2.1 Create Timeline_Engine models and TaskStatus enum
    - Implement `TimelineTemplate`, `TimelineInstance` (OneToOne to `OBECycle`), `Phase`, `Milestone`, `Task`, `ChecklistItem`, `TaskDependency` (kind hard|soft), `ScheduleChange`, and `OBECycle`
    - Implement the eight-member `TaskStatus` text choices and Task deadline fields (deadline_kind, fixed_date, relative_offset_days, relative_reference, resolved_deadline) and explanation fields (what/why/who/when/how/next)
    - Create migrations
    - _Requirements: 1.2, 2.1, 3.1, 3.4_

  - [ ] 2.2 Implement create_cycle_from_template deep-copy in TimelineService
    - Deep-copy every Phase, Milestone, Task, Checklist item, and dependency edge from template to instance within one transaction, remapping dependency references to new instance tasks, binding to a new OBE_Cycle, and recording Production_Readiness_Fields
    - Reject templates with no Phase via `DomainError` naming the missing structure and corrective step before any write
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [ ]* 2.3 Write property test and edge test for instantiation
    - **Property 1: Instantiation preserves template structure** (Validates: Requirements 1.1, 1.4)
    - **Property 2: Each instance binds to exactly one cycle** (Validates: Requirements 1.2)
    - Edge: reject template with no phase (1.5)

  - [ ] 2.4 Implement task status state machine and transitions
    - Implement `submit_task` (→ Diajukan), `return_task_for_revision` (→ Perlu Revisi), `complete_task` (→ Selesai when all checklist items complete), `transition_to_dikerjakan` (blocked by incomplete hard deps)
    - Implement `recompute_statuses`: derive Belum Siap / Siap Dikerjakan from hard-dependency completion and Terlambat from overdue-and-not-Selesai
    - _Requirements: 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 3.2_

  - [ ]* 2.5 Write property tests for task status lifecycle
    - **Property 4: Task status is always a valid enum value** (Validates: Requirements 2.1)
    - **Property 5: Belum Siap while a hard dependency is incomplete** (Validates: Requirements 2.2)
    - **Property 6: Siap Dikerjakan when all hard dependencies complete** (Validates: Requirements 2.3)
    - **Property 7: Overdue incomplete tasks become Terlambat** (Validates: Requirements 2.6)
    - **Property 8: Selesai only when marked complete and all checklist items complete** (Validates: Requirements 2.7)
    - **Property 9: Hard dependencies block Dikerjakan** (Validates: Requirements 3.2)
    - Example: submit → Diajukan (2.4), return → Perlu Revisi (2.5)

  - [ ] 2.6 Implement hard/soft dependency handling and advisories
    - Enforce hard-dependency blocking of Dikerjakan; for incomplete soft dependencies allow work and surface an advisory naming the incomplete predecessor
    - _Requirements: 3.1, 3.2, 3.3_

  - [ ]* 2.7 Write property test for soft dependencies
    - **Property 10: Soft dependencies advise but never block**
    - **Validates: Requirements 3.3**

  - [ ] 2.8 Implement fixed/relative deadlines and recomputation
    - Compute `resolved_deadline` from fixed date or relative offset + reference; recompute dependent relative deadlines when a referenced milestone/task date changes
    - _Requirements: 3.4, 3.5_

  - [ ]* 2.9 Write property test for relative deadlines
    - **Property 11: Relative deadlines track their reference**
    - **Validates: Requirements 3.5**

  - [ ] 2.10 Implement non-destructive schedule history
    - Implement `change_schedule` (retain previous value, require and store a reason, record actor/timestamp/previous/new, recompute dependent relative deadlines) and `get_history` returning entries newest-first
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [ ]* 2.11 Write property test for schedule history
    - **Property 14: Schedule history is non-destructive and ordered**
    - **Validates: Requirements 5.1, 5.2, 5.3, 5.4**

  - [ ] 2.12 Implement HomeService next-best-work grouping
    - Partition the current user's tasks into Do Now (Siap Dikerjakan/Dikerjakan), Next (Belum Siap), Waiting on Others (Diajukan), each with a complete six-facet explanation (what/why/who/when/how/next)
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [ ]* 2.13 Write property tests for Home grouping and explanations
    - **Property 12: Home grouping maps status to the correct bucket** (Validates: Requirements 4.1, 4.2, 4.3, 4.4)
    - **Property 13: Explanations are complete** (Validates: Requirements 4.5, 13.2, 14.1)

- [ ] 3. Checkpoint - Timeline_Engine
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 4. Implement Curriculum_Module
  - [ ] 4.1 Create Curriculum_Module models
    - Implement `Curriculum` (status draft|active|archived), `CPL`, `CPLIndicator` (numeric target_value), `Course`, `CourseCPLContribution` (contribution_level Introduce|Reinforce|Master, many-to-many course↔CPL)
    - Add a partial unique index `UNIQUE (prodi) WHERE status='active'`; create migrations; record Production_Readiness_Fields
    - _Requirements: 6.1, 6.2, 6.3, 6.6, 7.2, 7.3_

  - [ ] 4.2 Implement CurriculumService lifecycle and single-active enforcement
    - Implement `create_curriculum` and `activate_curriculum` enforcing at most one active curriculum per prodi, rejecting a second activation with a message naming the existing active curriculum and the corrective step; enforce draft/active/archived lifecycle
    - _Requirements: 6.4, 6.5, 6.6_

  - [ ]* 4.3 Write property tests for curriculum lifecycle
    - **Property 15: At most one active curriculum per prodi** (Validates: Requirements 6.4, 6.5)
    - **Property 16: Curriculum status stays within its lifecycle** (Validates: Requirements 6.6)

  - [ ] 4.4 Implement Course→CPL contribution mapping
    - Implement `map_course_to_cpl` requiring a contribution level in {Introduce, Reinforce, Master}, rejecting any other value with the allowed values listed; support many-to-many in both directions
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

  - [ ]* 4.5 Write property and unit tests for contribution mapping
    - **Property 17: Contribution level is constrained** (Validates: Requirements 7.1, 7.4)
    - Unit: curriculum→CPL→indicator cardinality (6.1), many-to-many course↔CPL (7.2, 7.3); Edge: reject invalid contribution level (7.4)

- [ ] 5. Implement RPS_Module
  - [ ] 5.1 Create RPS_Module models
    - Implement `RPS` (FKs to one Course, Curriculum, class, period), `CPMK` (M2M derived_from CPLs), `SubCPMK`, `SubCPMKIndicator`, `AssessmentInstrument`, `Rubric`, `RubricCriterion` (weight), `RubricLevel` (label, score), `RubricCriterion.mapped_indicators` M2M, `Score`
    - Create migrations; record Production_Readiness_Fields on RPS, Assessment_Instrument, and Rubric
    - _Requirements: 8.1, 8.3, 8.4, 9.1, 9.2, 9.3, 9.4_

  - [ ] 5.2 Implement RPS creation and CPMK derivation binding
    - Implement `create_rps` (bind to exactly one course/curriculum/class/period) and `add_cpmk` deriving only from CPLs of the bound curriculum (via CurriculumService), rejecting foreign CPLs with an explainable message
    - _Requirements: 8.1, 8.2, 8.5_

  - [ ]* 5.3 Write property and unit tests for RPS binding
    - **Property 18: CPMK derives only from bound-curriculum CPLs** (Validates: Requirements 8.2, 8.5)
    - Unit: CPMK→Sub_CPMK→indicators cardinality (8.3); Edge: reject CPMK from foreign CPL (8.5)

  - [ ] 5.4 Implement rubric definition and criterion→indicator mapping
    - Implement `define_rubric` creating criteria with levels/scores/weights and mapping each criterion to one or more Sub_CPMK indicators
    - _Requirements: 9.1, 9.2, 9.3_

  - [ ]* 5.5 Write unit tests for rubric structure
    - Test instrument→rubric cardinality (9.1) and criterion level/score/weight storage (9.2)
    - _Requirements: 9.1, 9.2_

  - [ ] 5.6 Implement submit_rps weight-sum and coverage validation
    - On `submit_rps`, verify each rubric's criterion weights sum to 100% (block with current/required sum) and every Sub_CPMK indicator maps to at least one criterion (block listing each unmapped indicator and corrective step)
    - _Requirements: 10.1, 10.2, 10.3, 10.4_

  - [ ]* 5.7 Write property tests for RPS submission validation
    - **Property 19: RPS submission requires weights summing to 100%** (Validates: Requirements 10.1, 10.3)
    - **Property 20: RPS submission requires full indicator coverage** (Validates: Requirements 10.2, 10.4)

- [ ] 6. Checkpoint - Curriculum and RPS modules
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 7. Implement Attainment_Engine
  - [ ] 7.1 Create Attainment_Engine models and formula config
    - Implement `CalculationFormula` (name, version, level, definition as versioned config) and `AttainmentResult` (outcome_ref, actual_value, target_value, gap, formula_name, formula_version, M2M traceability to Score)
    - Create migrations
    - _Requirements: 11.2, 11.3, 11.4, 18.2_

  - [ ] 7.2 Implement the attainment calculation chain
    - Implement `calculate` aggregating Rubric_Criterion → CPL_Indicator → Sub_CPMK → CPMK → CPL using named/versioned formulas (reading scores/outcomes via RPSService), storing actual/target/gap and formula identity, retaining traceability, running inside a transaction
    - _Requirements: 11.1, 11.2, 11.3, 11.4_

  - [ ]* 7.3 Write property tests for calculation results
    - **Property 21: Attainment results record formula identity and correct gap** (Validates: Requirements 11.2, 11.3)
    - **Property 22: Attainment results are traceable to source scores** (Validates: Requirements 11.1, 11.4)

  - [ ] 7.4 Implement data-integrity halt
    - Before aggregating, validate source data; halt (leaving existing results unchanged) on missing required scores or out-of-range scores, returning a message identifying the offending data and corrective step
    - _Requirements: 12.1, 12.2, 12.3_

  - [ ]* 7.5 Write property and edge tests for the halt behavior
    - **Property 23: Bad data halts calculation without side effects** (Validates: Requirements 12.1, 12.2, 12.3)
    - Edge: halt on missing/out-of-range score (12.1, 12.2)

  - [ ] 7.6 Implement gap-driven evaluation task creation
    - For each result where actual < target, create an evaluation Task in the cycle's Timeline_Instance via TimelineService, populated with a complete explanation (outcome, actual, target, gap); create none when actual ≥ target
    - _Requirements: 13.1, 13.2, 13.3_

  - [ ]* 7.7 Write property test for gap-driven tasks
    - **Property 24: Evaluation tasks are created exactly for unmet outcomes**
    - **Validates: Requirements 13.1, 13.3**

- [ ] 8. Checkpoint - Attainment_Engine
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 9. Implement Data_Injection_Tool and demo seed
  - [ ] 9.1 Implement idempotent, logged management commands and CSV/JSON importers
    - Implement Django management commands and CSV/JSON importers loading synthetic data via keyed ORM upserts (idempotent), writing a `DataInjectionLog` record per load/reset, using only the ORM with parameterized queries (no string-concatenated SQL)
    - _Requirements: 17.1, 17.2, 17.3, 17.4_

  - [ ] 9.2 Author demo seed scenarios
    - Seed demo Kaprodi and Lecturer accounts and a full vertical-loop scenario (template, cycle, curriculum, RPS with rubrics, scores) usable by the UI
    - _Requirements: 15.1, 17.1_

  - [ ]* 9.3 Write property and unit tests for data injection
    - **Property 27: Data injection is idempotent** (Validates: Requirements 17.2)
    - Unit: data injection writes a log record (17.3); static inspection: ORM/parameterized-query usage, no string-concatenated SQL (17.4)

  - [ ]* 9.4 Write property test for production-readiness fields
    - **Property 3: Production-readiness fields are always populated**
    - **Validates: Requirements 1.3, 6.3, 8.4, 9.4**

- [ ] 10. Implement UI workspaces (thin views + HTMX)
  - [ ] 10.1 Implement Home and Timeline workspaces
    - Build thin views calling HomeService and TimelineService: Home (Do Now/Next/Waiting on Others) and Timeline (cycles, templates, instances, phases, milestones, tasks, dependencies, history)
    - _Requirements: 4.1, 16.1, 18.4_

  - [ ] 10.2 Implement Curriculum and Learning workspaces with HTMX wizards
    - Build Curriculum workspace (curricula, CPLs, indicators, courses, contributions) and Learning workspace RPS authoring wizards (CPMK/Sub-CPMK, instruments, rubrics) with autosave: each step persists via the service layer before the next renders, with prefill on return
    - _Requirements: 16.1, 16.2, 16.3, 18.4_

  - [ ] 10.3 Implement Attainment & Quality workspace
    - Build thin views calling AttainmentService to run calculations and view actual/target/gap, traceability, and gap-driven tasks; confirm no more than five workspaces total
    - _Requirements: 16.1, 18.4_

  - [ ]* 10.4 Write property and structural tests for the UI layer
    - **Property 26: Wizard steps persist before advancing** (Validates: Requirements 16.2, 16.3)
    - Structural: views contain no business logic and call services (18.4); exactly five workspaces (16.1)

- [ ] 11. Integration and smoke tests, final wiring
  - [ ] 11.1 Wire modules, URLs, and cross-module service calls end to end
    - Register all app URLs, wire the base template/navigation for the five workspaces, and confirm Attainment→Timeline and RPS→Curriculum collaborations run through service interfaces only
    - _Requirements: 16.1, 18.4_

  - [ ]* 11.2 Write integration and smoke tests
    - Integration: `docker compose up -d --build` starts web + db and the app connects to the database (18.3)
    - Smoke: demo accounts seeded (15.1), Dev_Banner present (15.3), no auth enforcement (15.4), migrations applied not seed scripts (18.1)
    - _Requirements: 15.1, 15.3, 15.4, 18.1, 18.3_

- [ ] 12. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional test sub-tasks and can be skipped for a faster MVP; core implementation tasks are never optional.
- Every task references the specific requirements (and, for tests, the design properties) it implements for full traceability.
- All views are thin and call exactly one service method; business logic and validation live in the service layer and raise `DomainError` (Requirement 18.4).
- Cross-module calls go through service interfaces only (Attainment→Timeline, RPS→Curriculum), never through another module's ORM models.
- Property-based tests use Hypothesis (min. 100 iterations) and are tagged `Feature: obe-system, Property {n}: {text}`; example/edge/integration/smoke tests follow the design's testing strategy.
- Checkpoints ensure incremental validation after each major module.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "1.3", "1.4"] },
    { "id": 2, "tasks": ["1.5", "1.6", "2.1"] },
    { "id": 3, "tasks": ["2.2", "4.1", "5.1", "7.1"] },
    { "id": 4, "tasks": ["2.3", "2.4", "4.2", "5.2", "9.1"] },
    { "id": 5, "tasks": ["2.5", "2.6", "4.3", "4.4", "5.3", "5.4", "9.2"] },
    { "id": 6, "tasks": ["2.7", "2.8", "4.5", "5.5", "5.6", "7.2", "9.3"] },
    { "id": 7, "tasks": ["2.9", "2.10", "5.7", "7.3", "7.4", "9.4"] },
    { "id": 8, "tasks": ["2.11", "2.12", "7.5", "7.6"] },
    { "id": 9, "tasks": ["2.13", "7.7", "10.1", "10.2", "10.3"] },
    { "id": 10, "tasks": ["10.4", "11.1"] },
    { "id": 11, "tasks": ["11.2"] }
  ]
}
```
