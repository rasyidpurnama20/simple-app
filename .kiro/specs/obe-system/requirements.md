# Requirements Document

## Introduction

This document specifies the Minimum Viable Product (MVP) for an Outcome-Based Education (OBE) management system delivered as a modular monolith built with Django and PostgreSQL. The MVP proves the end-to-end architecture through one complete vertical loop: a Kaprodi drives an OBE Cycle through a timeline/workflow engine; a Lecturer authors curriculum structure and Learning Program Plans (RPS) with rubrics; grading through rubrics flows upward through a named, versioned calculation chain into learning-outcome attainment; and attainment gaps automatically generate follow-up evaluation work.

The system runs in a development-only environment with demo accounts, in-app role switching, synthetic data, and no real authentication or permission enforcement. Despite the development-only runtime, all persisted entities carry production-readiness metadata so the same data model can later be promoted to production without restructuring.

The following capabilities are explicitly out of scope for this MVP: the full 100-point maturity target, the GPM quality-review workflow, the student portal, the production security gate (HTTPS, secrets management, backup, monitoring, rollback), AI-driven features, and SSO or real permission enforcement. The design must not preclude later addition of a JSON API, GPM review, student views, or AI features.

## Glossary

- **OBE_System**: The complete Outcome-Based Education software system described in this document.
- **Timeline_Engine**: The subsystem that manages OBE Cycles, timeline templates, timeline instances (runs), phases, milestones, tasks, checklists, statuses, and dependencies.
- **Curriculum_Module**: The subsystem that manages academic structure, Program Learning Outcomes, courses, and course-to-outcome contribution mappings.
- **RPS_Module**: The subsystem that manages Learning Program Plans (RPS), course-level outcomes, assessment instruments, and rubrics.
- **Attainment_Engine**: The subsystem that computes outcome attainment from rubric scores using named, versioned formulas.
- **Data_Injection_Tool**: The set of official Django management commands and CSV/JSON import routines used to load or reset synthetic development data.
- **Role_Switcher**: The in-app mechanism that lets a demo user assume a different role without authenticating.
- **OBE_Cycle**: A time-bounded run of the outcome-based education process for a given program of study.
- **Timeline_Template**: A reusable definition of phases, milestones, tasks, checklists, and dependencies used to instantiate a Timeline_Instance.
- **Timeline_Instance**: A concrete run created from a Timeline_Template and bound to an OBE_Cycle. Also called a "run".
- **Phase**: A top-level stage within a Timeline_Instance that groups milestones.
- **Milestone**: A dated checkpoint within a Phase that groups tasks.
- **Task**: A unit of work with an owner, status, dependencies, and explanatory guidance.
- **Checklist**: An ordered set of completion items belonging to a Task.
- **Hard_Dependency**: A dependency that blocks a Task from becoming workable until its predecessor is complete.
- **Soft_Dependency**: An advisory dependency that produces a recommendation but does not block work.
- **Fixed_Date**: A deadline expressed as an absolute calendar date.
- **Relative_Date**: A deadline expressed as an offset from a reference date such as a Milestone date.
- **Task_Status**: One of the human-friendly statuses: Belum Siap, Siap Dikerjakan, Dikerjakan, Diajukan, Perlu Revisi, Selesai, Terhambat, Terlambat.
- **CPL**: Capaian Pembelajaran Lulusan (Program Learning Outcome), each with indicators and targets.
- **CPL_Indicator**: A measurable indicator belonging to a CPL, carrying a numeric target value.
- **Curriculum**: A versioned collection of CPLs and courses scoped to a program of study.
- **Course**: An academic subject within a Curriculum.
- **Contribution_Level**: The degree to which a Course addresses a CPL, one of Introduce, Reinforce, or Master.
- **RPS**: Rencana Pembelajaran Semester (Learning Program Plan) bound to a Course, Curriculum, class, and academic period.
- **CPMK**: Capaian Pembelajaran Mata Kuliah (Course Learning Outcome), derived from CPL.
- **Sub_CPMK**: A sub-outcome of a CPMK, carrying indicators.
- **Assessment_Instrument**: A graded activity (for example an assignment or exam) defined within an RPS.
- **Rubric**: A scoring guide belonging to an Assessment_Instrument, composed of criteria, levels, scores, and weights.
- **Rubric_Criterion**: A single scored dimension of a Rubric, mapped to one or more outcomes.
- **Calculation_Formula**: A named, versioned rule that aggregates scores at one level of the attainment chain.
- **Attainment_Result**: The computed actual value, target value, and gap for an outcome, with traceability to source evidence.
- **Kaprodi**: The program-of-study head who owns the OBE_Cycle and its timeline.
- **Lecturer**: The teaching staff member (Pengampu) who authors RPS and grades through rubrics.
- **Dev_Administrator**: The development operator who seeds and resets synthetic data.
- **Production_Readiness_Fields**: The metadata set stored on every entity: program of study (prodi), owner, status, version, creator, created-time, and modified-time.
- **Dev_Banner**: A persistent visual indicator shown in the interface stating that the environment is a development environment with synthetic data.

## Requirements

### Requirement 1: OBE Cycle and Timeline Templates

**User Story:** As a Kaprodi, I want to create an OBE Cycle from a reusable timeline template, so that each cycle starts from a consistent, complete workflow structure.

#### Acceptance Criteria

1. WHEN a Kaprodi creates an OBE_Cycle from a Timeline_Template, THE Timeline_Engine SHALL create a Timeline_Instance containing every Phase, Milestone, Task, and Checklist defined in the Timeline_Template.
2. THE Timeline_Engine SHALL bind each Timeline_Instance to exactly one OBE_Cycle.
3. WHEN a Kaprodi creates an OBE_Cycle, THE Timeline_Engine SHALL record the Production_Readiness_Fields for the OBE_Cycle.
4. WHERE a Timeline_Template defines a Task dependency, THE Timeline_Engine SHALL copy that dependency into the corresponding Task of the Timeline_Instance.
5. IF a Kaprodi attempts to create an OBE_Cycle from a Timeline_Template that contains no Phase, THEN THE Timeline_Engine SHALL reject the creation and return a message that identifies the missing structure and the corrective step.

### Requirement 2: Task Status Lifecycle

**User Story:** As a Kaprodi, I want tasks to move through human-friendly statuses, so that every participant understands the state of each piece of work without technical jargon.

#### Acceptance Criteria

1. THE Timeline_Engine SHALL restrict each Task_Status to one of: Belum Siap, Siap Dikerjakan, Dikerjakan, Diajukan, Perlu Revisi, Selesai, Terhambat, Terlambat.
2. WHEN a Task is created and at least one Hard_Dependency of the Task is not Selesai, THE Timeline_Engine SHALL set the Task_Status to Belum Siap.
3. WHEN every Hard_Dependency of a Task reaches Selesai, THE Timeline_Engine SHALL set the Task_Status of that Task to Siap Dikerjakan.
4. WHEN a Lecturer submits a Task for review, THE Timeline_Engine SHALL set the Task_Status to Diajukan.
5. WHEN a reviewer returns a Diajukan Task for changes, THE Timeline_Engine SHALL set the Task_Status to Perlu Revisi.
6. IF the current date is later than the deadline of a Task whose Task_Status is not Selesai, THEN THE Timeline_Engine SHALL set the Task_Status to Terlambat.
7. WHEN a Task is marked complete and every Checklist item of the Task is complete, THE Timeline_Engine SHALL set the Task_Status to Selesai.

### Requirement 3: Task Dependencies and Deadlines

**User Story:** As a Kaprodi, I want to define hard and soft dependencies with fixed or relative deadlines, so that the workflow enforces true blockers while advising on soft ordering.

#### Acceptance Criteria

1. THE Timeline_Engine SHALL classify each Task dependency as either a Hard_Dependency or a Soft_Dependency.
2. WHILE a Hard_Dependency of a Task is not Selesai, THE Timeline_Engine SHALL prevent the dependent Task from entering the Dikerjakan status.
3. WHERE a Soft_Dependency of a Task is not Selesai, THE Timeline_Engine SHALL allow work on the dependent Task and SHALL present an advisory recommendation that names the incomplete predecessor.
4. THE Timeline_Engine SHALL express each Task deadline as either a Fixed_Date or a Relative_Date.
5. WHEN a Relative_Date reference changes, THE Timeline_Engine SHALL recompute the resolved deadline of each Task that uses that reference.

### Requirement 4: Next Best Work and Home Workspace

**User Story:** As a Kaprodi or Lecturer, I want the Home workspace to show what to do now, what is next, and what is waiting on others, so that I always know my next action.

#### Acceptance Criteria

1. THE OBE_System SHALL present a Home workspace that groups the current user's Tasks into "Do Now", "Next", and "Waiting on Others".
2. WHEN a Task assigned to the current user has Task_Status Siap Dikerjakan or Dikerjakan, THE OBE_System SHALL place that Task in the "Do Now" group.
3. WHEN a Task assigned to the current user has Task_Status Belum Siap, THE OBE_System SHALL place that Task in the "Next" group.
4. WHEN a Task assigned to the current user has Task_Status Diajukan, THE OBE_System SHALL place that Task in the "Waiting on Others" group.
5. THE OBE_System SHALL present, for each Task, an explanation that states what the Task is, why it matters, who owns it, when it is due, how to complete it, and what follows it.

### Requirement 5: Timeline History and Audit

**User Story:** As a Kaprodi, I want every schedule change to be recorded with a reason, so that the full history of the timeline remains traceable and no prior schedule is lost.

#### Acceptance Criteria

1. WHEN a Kaprodi changes the deadline of a Milestone or Task, THE Timeline_Engine SHALL retain the previous deadline as a historical record rather than overwriting it.
2. WHEN a Kaprodi changes a schedule, THE Timeline_Engine SHALL require a reason and SHALL store the reason with the historical record.
3. THE Timeline_Engine SHALL record the actor, timestamp, previous value, and new value for each schedule change.
4. WHEN a user requests the history of a Timeline_Instance, THE Timeline_Engine SHALL return the recorded changes in reverse chronological order.

### Requirement 6: Curriculum and CPL Structure

**User Story:** As a Lecturer, I want to define curriculum structure with program learning outcomes, indicators, and targets, so that courses and assessments can be aligned to measurable outcomes.

#### Acceptance Criteria

1. THE Curriculum_Module SHALL allow a Curriculum to contain CPLs, and SHALL allow each CPL to contain one or more CPL_Indicators.
2. THE Curriculum_Module SHALL store a numeric target value for each CPL_Indicator.
3. THE Curriculum_Module SHALL record the Production_Readiness_Fields for each Curriculum, CPL, and Course.
4. WHILE a Curriculum has status active, THE Curriculum_Module SHALL allow at most one active Curriculum per program of study.
5. IF a Lecturer attempts to activate a second Curriculum for a program of study that already has an active Curriculum, THEN THE Curriculum_Module SHALL reject the activation and return a message identifying the existing active Curriculum and the corrective step.
6. THE Curriculum_Module SHALL restrict each Curriculum to a status lifecycle of draft, active, and archived.

### Requirement 7: Course-to-CPL Contribution

**User Story:** As a Lecturer, I want to map each course to the CPLs it addresses with a contribution level, so that the curriculum shows where each outcome is introduced, reinforced, and mastered.

#### Acceptance Criteria

1. WHEN a Lecturer maps a Course to a CPL, THE Curriculum_Module SHALL require a Contribution_Level of Introduce, Reinforce, or Master.
2. THE Curriculum_Module SHALL allow a Course to contribute to more than one CPL.
3. THE Curriculum_Module SHALL allow more than one Course to contribute to the same CPL.
4. IF a Lecturer maps a Course to a CPL with a Contribution_Level other than Introduce, Reinforce, or Master, THEN THE Curriculum_Module SHALL reject the mapping and return a message that lists the allowed values.

### Requirement 8: RPS Authoring and Binding

**User Story:** As a Lecturer, I want to author an RPS bound to a specific course, curriculum, class, and academic period, so that each learning plan is anchored to its academic context.

#### Acceptance Criteria

1. WHEN a Lecturer creates an RPS, THE RPS_Module SHALL bind the RPS to exactly one Course, one Curriculum, one class, and one academic period.
2. THE RPS_Module SHALL allow each CPMK within an RPS to be derived from one or more CPLs of the bound Curriculum.
3. THE RPS_Module SHALL allow each CPMK to contain one or more Sub_CPMKs, and SHALL allow each Sub_CPMK to carry one or more indicators.
4. THE RPS_Module SHALL record the Production_Readiness_Fields for each RPS.
5. IF a Lecturer creates a CPMK derived from a CPL that does not belong to the bound Curriculum, THEN THE RPS_Module SHALL reject the derivation and return a message identifying the invalid CPL and the corrective step.

### Requirement 9: Assessment Instruments and Rubrics

**User Story:** As a Lecturer, I want to define assessment instruments with rubrics whose criteria map to outcomes, so that grading directly produces outcome evidence.

#### Acceptance Criteria

1. THE RPS_Module SHALL allow each Assessment_Instrument to contain one Rubric composed of Rubric_Criteria.
2. THE RPS_Module SHALL store, for each Rubric_Criterion, its achievement levels, the score for each level, and the criterion weight.
3. THE RPS_Module SHALL allow each Rubric_Criterion to be mapped to one or more Sub_CPMK indicators.
4. THE RPS_Module SHALL record the Production_Readiness_Fields for each Assessment_Instrument and Rubric.

### Requirement 10: Rubric Weight and Coverage Validation

**User Story:** As a Lecturer, I want the system to check rubric weights and outcome coverage before I submit an RPS, so that grading produces complete and correctly weighted outcome evidence.

#### Acceptance Criteria

1. WHEN a Lecturer submits an RPS for review, THE RPS_Module SHALL verify that the criterion weights of each Rubric sum to 100 percent.
2. WHEN a Lecturer submits an RPS for review, THE RPS_Module SHALL verify that every Sub_CPMK indicator of the RPS is mapped to at least one Rubric_Criterion.
3. IF the criterion weights of a Rubric do not sum to 100 percent, THEN THE RPS_Module SHALL block the submission and return a message that states the current sum and the required sum.
4. IF a Sub_CPMK indicator is not mapped to any Rubric_Criterion, THEN THE RPS_Module SHALL block the submission and return a message that identifies each unmapped indicator and the corrective step.

### Requirement 11: Attainment Calculation Chain

**User Story:** As a Kaprodi, I want attainment computed from rubric scores up through the outcome hierarchy using named, versioned formulas, so that results are reproducible and auditable.

#### Acceptance Criteria

1. WHEN a Kaprodi requests an attainment calculation for an OBE_Cycle, THE Attainment_Engine SHALL aggregate scores along the chain Rubric_Criterion to CPL_Indicator to Sub_CPMK to CPMK to CPL.
2. THE Attainment_Engine SHALL apply a named, versioned Calculation_Formula at each aggregation level and SHALL record the formula name and version used in each Attainment_Result.
3. THE Attainment_Engine SHALL store, for each Attainment_Result, the actual value, the target value, and the gap between the actual value and the target value.
4. THE Attainment_Engine SHALL retain traceability from each Attainment_Result to the rubric scores that produced it.

### Requirement 12: Calculation Data Integrity Halt

**User Story:** As a Kaprodi, I want the calculation to halt on bad source data, so that no attainment result is produced from incomplete or invalid inputs.

#### Acceptance Criteria

1. IF a required rubric score is missing when an attainment calculation runs, THEN THE Attainment_Engine SHALL halt the calculation and SHALL return a message that identifies the missing source data and the corrective step.
2. IF a source score falls outside the range defined by its Rubric_Criterion, THEN THE Attainment_Engine SHALL halt the calculation and SHALL return a message that identifies the invalid score and the corrective step.
3. WHEN the Attainment_Engine halts a calculation, THE Attainment_Engine SHALL leave existing Attainment_Results unchanged.

### Requirement 13: Gap-Driven Evaluation Tasks

**User Story:** As a Kaprodi, I want attainment gaps to automatically generate evaluation tasks, so that unmet outcomes are followed up as tracked work in the timeline.

#### Acceptance Criteria

1. WHEN an Attainment_Result has an actual value below its target value, THE Attainment_Engine SHALL generate an evaluation Task in the Timeline_Instance of the OBE_Cycle.
2. THE Attainment_Engine SHALL populate each generated evaluation Task with an explanation that identifies the outcome, the actual value, the target value, and the gap.
3. WHEN an Attainment_Result has an actual value at or above its target value, THE Attainment_Engine SHALL NOT generate an evaluation Task for that Attainment_Result.

### Requirement 14: Explainable Rules and Validation Messages

**User Story:** As a Kaprodi or Lecturer, I want tasks and validation messages to explain themselves in plain language, so that I can act without technical support.

#### Acceptance Criteria

1. THE OBE_System SHALL present, for each generated Task, an explanation of what the Task is, why it matters, who owns it, when it is due, how to complete it, and what follows it.
2. WHEN the OBE_System rejects a user action through validation, THE OBE_System SHALL return a message that states the problem and the corrective step.
3. THE OBE_System SHALL express validation messages in plain language without database or internal system terminology.

### Requirement 15: Development Environment and Role Switching

**User Story:** As a Dev Administrator, I want demo accounts with in-app role switching and a development banner, so that stakeholders can exercise the full loop without real authentication.

#### Acceptance Criteria

1. THE OBE_System SHALL provide demo accounts for the Kaprodi and Lecturer roles.
2. WHEN a user selects a different role through the Role_Switcher, THE OBE_System SHALL present the interface and available actions of the selected role.
3. THE OBE_System SHALL display a Dev_Banner stating that the environment is a development environment using synthetic data.
4. THE OBE_System SHALL operate without real authentication, SSO, or permission enforcement.

### Requirement 16: Workspace Structure

**User Story:** As a user, I want a small fixed set of workspaces where each screen presents one decision, so that the interface stays work-centered and uncluttered.

#### Acceptance Criteria

1. THE OBE_System SHALL organize its interface into the workspaces Home, Timeline, Curriculum, Learning, and Attainment & Quality, and SHALL NOT present more than five workspaces.
2. WHERE a user authoring flow spans multiple steps, THE OBE_System SHALL present the flow as a wizard with autosave and field prefill.
3. WHEN a user advances a wizard step, THE OBE_System SHALL save the entered data before presenting the next step.

### Requirement 17: Development Data Injection

**User Story:** As a Dev Administrator, I want official, logged, idempotent commands to load and reset synthetic data, so that the demo environment can be populated and reset safely.

#### Acceptance Criteria

1. THE Data_Injection_Tool SHALL load synthetic data through official Django management commands or CSV/JSON import routines.
2. WHEN a data-load command runs more than once with the same input, THE Data_Injection_Tool SHALL leave the resulting data set identical to a single run.
3. WHEN the Data_Injection_Tool loads or resets data, THE Data_Injection_Tool SHALL write a log record of the operation.
4. THE Data_Injection_Tool SHALL compose database statements through the framework data-access layer using parameterized queries rather than string-concatenated SQL.

### Requirement 18: Schema, Configuration, and Deployment

**User Story:** As a Dev Administrator, I want schema managed by migrations, rules stored as versioned configuration, and a single-command startup, so that the system installs and evolves predictably.

#### Acceptance Criteria

1. THE OBE_System SHALL apply all database schema changes through Django migrations rather than seed scripts.
2. THE OBE_System SHALL store standards, Calculation_Formulas, and validation rules as versioned configuration records.
3. WHEN a Dev Administrator runs the command `docker compose up -d --build`, THE OBE_System SHALL start a web container and a database container.
4. THE OBE_System SHALL separate request-handling views from a service layer so that a JSON API can be added without changing the service layer.
