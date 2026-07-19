# Traceability PR-01–PR-88

`Baseline` berarti artefak kode/schema/service/konfigurasi awal tersedia dalam PR ini. Acceptance lapangan, integrasi institusi, benchmark, dan sign-off yang memerlukan lingkungan nyata tetap berstatus `Gate lanjutan` sebagaimana dirinci di `IMPLEMENTATION_STATUS.md`.

| PR | Requirement | Implementasi utama | Status |
|---|---|---|---|
| 01 | Baseline dan arsitektur | `docs/ARCHITECTURE.md`, paket domain | Baseline |
| 02 | Struktur dan batas modul | `obe/*`, `tests/test_architecture.py` | Baseline |
| 03 | CI dan quality gate | `.github/workflows/ci.yml`, PR template | Baseline |
| 04 | Environment dan secret | lima profil settings, validasi fail-fast, SOPS, redaksi, rotasi/revokasi, `PR04_ACCEPTANCE.md` | Implemented |
| 05 | Deployment reproducible | digest preflight, server/edge Compose, Ansible, idempotent ops, `PR05_PR07_ACCEPTANCE.md` | Implemented |
| 06 | PostgreSQL source of truth | connection limits, actor/version migrations, optimistic lock, query budget | Implemented |
| 07 | Evidence immutable | private CAS, ClamAV, quota, token access, audit, Restic/restore verification | Implemented |
| 08 | Valkey/RabbitMQ/Celery | queue policy bounded/DLQ, worker isolation, idempotent job/lease/cancel, `PR08_PR10_ACCEPTANCE.md` | Implemented |
| 09 | Transactional outbox | standardized envelope, retry/dead publisher, inbox/cursor consumer, reconciliation | Implemented |
| 10 | Observability dan SLO | OTLP app instrumentation, Collector/Prometheus/Loki/Tempo/Grafana, alerts/dashboard/redaction | Implemented |
| 11 | Security baseline | layered middleware/Nginx, deny-by-default zones, admin VPN/key, security tests, `PR11_PR14_ACCEPTANCE.md` | Implemented |
| 12 | Identity/RBAC/scope | account lock/MFA/reset, scoped assignment, permission epoch dan background snapshot | Implemented |
| 13 | Audit append-only | complete audit context, redaction/separation, DB guard, hash-chain, signed export/retention | Implemented |
| 14 | Feature flag | versioned state/scope, activation evidence, cache invalidation, kill switch/job snapshot | Implemented |
| 15 | Academic rule registry | `shared.AcademicRule`, deterministic decision | Baseline |
| 16 | Cohort rule packages | `shared.rules` grade/SKS/graduation | Baseline |
| 17 | Explanation/override/appeal | decision trace dan audit primitives | Baseline |
| 18 | Academic integrity validation | `quality.IntegrityIssue` | Baseline |
| 19 | Curriculum versions | `curriculum.CurriculumVersion`, checksum | Baseline |
| 20 | 5 PL dan 12 CPL | idempotent `seed_demo` | Baseline |
| 21 | 18 bahan kajian dan depth | idempotent `seed_demo`, `Outcome.depth` | Baseline |
| 22 | 77 courses dan semester map | idempotent `seed_demo`, 126 SKS wajib | Baseline |
| 23 | 31 CPMK | idempotent `seed_demo` | Baseline |
| 24 | Weighted traceability | `CurriculumEdge`, allocation validator | Baseline |
| 25 | Versioned RPS approval | `learning.RPSVersion`, publish service | Baseline |
| 26 | CPMK-RPS/Sub-CPMK/indicator | versioned RPS semantic content | Baseline |
| 27 | Weekly plan | `learning.WeeklyPlan` minggu 1–16 | Baseline |
| 28 | Assessment blueprint | `AssessmentInstrument.mappings/rubric` | Baseline |
| 29 | Rubric/item/grading | assessment schema dan grading service | Baseline |
| 30 | Parallel class/exam | `CourseOffering.parallel_group` | Baseline |
| 31 | Grade normalization | score model dan boundary-tested rules | Baseline |
| 32 | Attendance eligibility | attendance service, boundary 75% | Baseline |
| 33 | Submission/evidence/feedback | `Submission`, `Score`, `EvidenceRecord` | Baseline |
| 34 | Attainment calculation | `AttainmentSnapshot` trace/source version | Baseline |
| 35 | Bidirectional OBE chain | versioned edge + source/trace fields | Baseline |
| 36 | Portfolio | reproducible evidence/attainment primitives | Baseline |
| 37 | Provus/CQI | `IntegrityIssue`, `ImprovementAction` | Baseline |
| 38 | PPEPP report | `QualityCycle` | Baseline |
| 39 | Academic feedback/action | quality issue/evidence/owner workflow | Baseline |
| 40 | Semantic JSON contract | analytics serializer/view/contract tests | Baseline |
| 41 | Local Apache ECharts | npm-pinned local bundle + reusable JS lifecycle | Baseline |
| 42 | Accessibility/privacy/cache/export | table fallback, ETag, private cache, CSP | Baseline |
| 43 | Sankey | semantic edge contract foundation | Gate lanjutan |
| 44 | Sunburst | allocation/completeness foundation | Gate lanjutan |
| 45 | Distribution/scatter | semantic metric selector foundation | Gate lanjutan |
| 46 | Coverage heatmap | mapping/status foundation | Gate lanjutan |
| 47 | Correlation heatmap | semantic dataset foundation | Gate lanjutan |
| 48 | CPL radar | local chart/table dashboard component | Baseline |
| 49 | BK/course treemap dan progress | curriculum/progress service foundation | Gate lanjutan |
| 50 | Integrated analytics dashboard | role-aware dashboard shell, common API | Baseline |
| 51 | Academic calendar | timezone/business-day config foundation | Gate lanjutan |
| 52 | Timeline/task engine | `TaskInstance`, dependency/idempotency | Baseline |
| 53 | Reminder/escalation | `Notification`, Celery beat | Baseline |
| 54 | Notification center/My Tasks | HTMX task list dan server state | Baseline |
| 55 | AI control plane | single `ai.gateway` → LiteLLM | Baseline |
| 56 | AI data policy/quota/access | data-class routing guard | Baseline |
| 57 | AI job/backpressure/fallback | Celery queues + explained fallback | Baseline |
| 58 | Prompt registry/evaluation | `PromptTemplate`, `AIRun` | Baseline |
| 59 | AI curriculum mapper | deterministic curriculum report foundation | Gate lanjutan |
| 60 | AI GPM checker | deterministic issue foundation | Gate lanjutan |
| 61 | AI teaching copilot | prompt/draft/human decision foundation | Gate lanjutan |
| 62 | AI learning coach | permission/data-class guard foundation | Gate lanjutan |
| 63 | AI-off gate | settings kill switch dan automated test | Baseline |
| 64 | Secure Exam authoring | `secure_exam.Exam`, maker-checker validation | Baseline |
| 65 | Signed/encrypted bundle | AES-GCM encryption, HMAC signature, checksum | Baseline |
| 66 | Exam Edge deployment | isolated Edge Compose/settings | Baseline |
| 67 | SEB/VLAN | isolated networks and operations contract | Gate lanjutan |
| 68 | Offline participant/session | `ExamSession` identity/device constraints | Baseline |
| 69 | Autosave/recovery | versioned `ExamResponse`, idempotency | Baseline |
| 70 | Result sync/reconciliation | integration staging/idempotency schema | Baseline |
| 71 | Exam go/no-go rehearsal | status document and Edge gate | Gate lanjutan |
| 72 | Academic status/leave | `AcademicStatus` effective versions | Baseline |
| 73 | IRS/SKS limit | `EnrollmentPlan`, tested decision service | Baseline |
| 74 | Scheduling/resources | offering schedule/room/capacity foundation | Baseline |
| 75 | Credits/GPA/results | best-attempt progress service | Baseline |
| 76 | Progress/graduation eligibility | deterministic graduation decision | Baseline |
| 77 | MBKM registry/eligibility | versioned rule/profile foundation | Gate lanjutan |
| 78 | MBKM conversion/report | result source/trace/integration foundation | Gate lanjutan |
| 79 | Recognition/competition/project | versioned result/evidence foundation | Gate lanjutan |
| 80 | PKL | curriculum seed + task/evidence/rule foundation | Gate lanjutan |
| 81 | KKN | curriculum seed + task/evidence/rule foundation | Gate lanjutan |
| 82 | Thesis eligibility/topic/lab | curriculum/rule/task foundation | Gate lanjutan |
| 83 | Thesis supervision/exam/revision | task/exam/evidence foundation | Gate lanjutan |
| 84 | Equivalence/transition | versioned result/trace foundation | Gate lanjutan |
| 85 | Institutional integration | `IntegrationBatch`, staging/reconciliation | Baseline |
| 86 | Performance/security/backup/DR | SLO, security, operation runbook | Gate lanjutan |
| 87 | UAT/accessibility/release gate | tests, local assets, status docs | Gate lanjutan |
| 88 | Go-live/hypercare/handover | feature flags and operations checklist | Gate lanjutan |
