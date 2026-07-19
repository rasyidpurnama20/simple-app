import hashlib
import json
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from obe.identity.services import ensure_demo_assignments
from obe.shared.academic_rules import sample_rule_registry

EXPECTED_SCHEMA = "5.0.0"
DEFAULT_FIXTURE = (
    Path(settings.BASE_DIR) / "fixtures" / "sample-data-2020-2026-obe-spec-v5.compact.json"
)
EXPECTED_COUNTS = {
    "graduateProfiles": 5,
    "cpl": 12,
    "knowledgeAreas": 18,
    "cpmk": 31,
    "courses": 77,
}
NAMESPACE = uuid.UUID("8d99f774-e2ad-44fb-8d48-f47bb1d03ea8")
ENROLLMENT_STATUSES = {"completed", "planned", "upcoming"}
RECONCILIATION_COVERAGE = {
    "curriculum_versions": "curricula",
    "graduate_profiles": "pl",
    "cpl": "cpl",
    "knowledge_areas": "bk",
    "cpmk": "cpmk",
    "courses": "courses",
    "rule_packages": "rule_packages",
    "academic_rules": "academic_rules",
    "students": "students",
    "semester_records": "plans",
    "course_enrollments_completed": "results",
    "lecturers": None,
    "course_offerings": "course_offerings",
    "rps_versions": "rps_versions",
    "course_outcomes": "rps_course_outcomes",
    "sub_outcomes": "rps_sub_outcomes",
    "indicators": "rps_indicators",
    "weekly_plans": "weekly_plans",
    "assessment_plans": "assessment_instruments",
    "rubrics": "rubrics",
    "evidence_manifests": None,
    "evidence_submissions": None,
    "evidence_scores": None,
    "decision_overrides": None,
    "feature_flags": None,
    "audit_events": None,
    "quality_issues": None,
    "provus_standards": None,
    "provus_findings": None,
    "ai_prompts": None,
    "secure_exams": None,
    "lifecycle_applications": None,
    "scoped_assignments": None,
    "integration_contracts": None,
}


def stable_uuid(*parts: object) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, ":".join(str(part) for part in parts))


def parse_date(value):
    if isinstance(value, str):
        return date.fromisoformat(value)
    return value or None


def decimal(value, default="0") -> Decimal:
    return Decimal(str(default if value is None else value))


def enrollment_status(enrollment: dict) -> str:
    """Normalize v5 enrollment state while retaining compact-fixture compatibility."""
    status = enrollment.get("status")
    if status in {None, ""}:
        return "completed" if enrollment.get("grade") is not None else "planned"
    return str(status).strip().lower()


def source_inventory(dataset: dict) -> dict[str, int]:
    students = dataset.get("students", [])
    semester_record_count = 0
    enrollment_count = 0
    enrollment_status_counts: dict[str, int] = defaultdict(int)
    for student in students:
        for semester in student.get("semesterRecords", []):
            semester_record_count += 1
            for enrollment in semester.get("courseEnrollments", []):
                enrollment_count += 1
                enrollment_status_counts[enrollment_status(enrollment)] += 1
    inventory = {
        "curriculum_versions": len(dataset.get("curriculumVersions", [])),
        "graduate_profiles": len(dataset.get("graduateProfiles", [])),
        "cpl": len(dataset.get("cpl", [])),
        "knowledge_areas": len(dataset.get("knowledgeAreas", [])),
        "cpmk": len(dataset.get("cpmk", [])),
        "courses": len(dataset.get("courses", [])),
        "rule_packages": len(dataset.get("academicRuleRegistry", {}).get("rulePackages", [])),
        "academic_rules": len(dataset.get("academicRuleRegistry", {}).get("rules", [])),
        "students": len(students),
        "semester_records": semester_record_count,
        "course_enrollments": enrollment_count,
        "lecturers": len(dataset.get("lecturers", [])),
        "course_offerings": len(dataset.get("courseOfferings", [])),
        "rps_versions": len(dataset.get("learning", {}).get("rpsVersions", [])),
        "course_outcomes": len(dataset.get("learning", {}).get("courseOutcomes", [])),
        "sub_outcomes": len(dataset.get("learning", {}).get("subOutcomes", [])),
        "indicators": len(dataset.get("learning", {}).get("indicators", [])),
        "weekly_plans": len(dataset.get("learning", {}).get("weeklyPlans", [])),
        "assessment_plans": len(dataset.get("assessment", {}).get("assessmentPlans", [])),
        "rubrics": len(dataset.get("assessment", {}).get("rubricLibrary", [])),
        "evidence_manifests": len(dataset.get("evidence", {}).get("manifests", [])),
        "evidence_submissions": len(dataset.get("evidence", {}).get("submissions", [])),
        "evidence_scores": len(dataset.get("evidence", {}).get("scoreRecords", [])),
        "decision_overrides": len(dataset.get("academicDecisions", {}).get("overrides", [])),
        "feature_flags": len(dataset.get("featureFlags", [])),
        "audit_events": len(dataset.get("auditTrail", {}).get("events", [])),
        "quality_issues": len(dataset.get("quality", {}).get("issues", [])),
        "provus_standards": len(dataset.get("quality", {}).get("provusStandards", [])),
        "provus_findings": len(dataset.get("quality", {}).get("provusFindings", [])),
        "ai_prompts": len(dataset.get("ai", {}).get("promptRegistry", [])),
        "secure_exams": len(dataset.get("secureExam", {}).get("examDefinitions", [])),
        "lifecycle_applications": len(dataset.get("academicLifecycle", {}).get("applications", [])),
        "scoped_assignments": len(dataset.get("identity", {}).get("scopedAssignments", [])),
        "integration_contracts": len(dataset.get("integration", {}).get("contracts", [])),
    }
    for status in sorted(ENROLLMENT_STATUSES):
        inventory[f"course_enrollments_{status}"] = enrollment_status_counts[status]
    return inventory


def enrollment_contract_errors(dataset: dict) -> list[str]:
    """Return bounded, actionable errors before the transaction writes any domain row."""
    course_codes = {item["code"] for item in dataset.get("courses", [])}
    errors: list[str] = []
    error_count = 0
    for student in dataset.get("students", []):
        for semester in student.get("semesterRecords", []):
            for enrollment in semester.get("courseEnrollments", []):
                status = enrollment_status(enrollment)
                context = (
                    f"student={student.get('nim')} semester={semester.get('semesterNumber')} "
                    f"course={enrollment.get('courseCode')}"
                )
                finding = ""
                if status not in ENROLLMENT_STATUSES:
                    finding = f"status enrollment tidak dikenal: {status!r}"
                elif enrollment.get("courseCode") not in course_codes:
                    finding = "referensi mata kuliah tidak ditemukan"
                elif status == "completed" and enrollment.get("grade") is None:
                    finding = "completed enrollment wajib memiliki grade"
                elif status == "completed" and enrollment.get("gradePoint") is None:
                    finding = "completed enrollment wajib memiliki gradePoint"
                elif status == "completed" and not enrollment.get("recordId"):
                    finding = "completed enrollment wajib memiliki recordId"
                if finding:
                    error_count += 1
                    if len(errors) < 20:
                        errors.append(f"{context}: {finding}")
    if error_count > len(errors):
        errors.append(f"... {error_count - len(errors)} error lain tidak ditampilkan")
    return errors


def write_reconciliation(path: Path, reconciliation: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(reconciliation, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        raise CommandError(f"Laporan rekonsiliasi tidak dapat ditulis: {exc}") from exc


def load_dataset(path: Path) -> tuple[dict, str]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise CommandError(f"Dataset tidak dapat dibaca: {path}: {exc}") from exc
    try:
        dataset = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CommandError(
            f"Dataset bukan JSON lengkap pada byte {exc.pos}: {exc.msg}. "
            "Unggah ulang file sumber atau gunakan fixture compact bawaan."
        ) from exc
    if dataset.get("schemaVersion") != EXPECTED_SCHEMA:
        raise CommandError(
            f"schemaVersion harus {EXPECTED_SCHEMA}, ditemukan {dataset.get('schemaVersion')!r}"
        )
    missing = [key for key in (*EXPECTED_COUNTS, "program") if key not in dataset]
    if missing:
        raise CommandError(f"Bagian dataset wajib tidak tersedia: {', '.join(missing)}")
    invalid_counts = {
        key: len(dataset[key])
        for key, count in EXPECTED_COUNTS.items()
        if len(dataset[key]) != count
    }
    if invalid_counts:
        raise CommandError(f"Jumlah katalog v5 tidak sesuai kontrak: {invalid_counts}")
    contract_errors = enrollment_contract_errors(dataset)
    if contract_errors:
        raise CommandError(
            "Kontrak enrollment v5 tidak valid sebelum import: " + "; ".join(contract_errors)
        )
    return dataset, hashlib.sha256(raw).hexdigest()


def proportional_allocations(
    targets: list[tuple[str, Decimal]],
) -> list[tuple[str, Decimal]]:
    signals: dict[str, Decimal] = defaultdict(Decimal)
    for target, signal in targets:
        if signal > 0:
            signals[target] += signal
    if not signals:
        return []
    ordered = sorted(signals.items())
    total = sum(signals.values(), Decimal("0"))
    values = [
        (target, (signal / total * Decimal("100")).quantize(Decimal("0.0001")))
        for target, signal in ordered[:-1]
    ]
    used = sum((weight for _, weight in values), Decimal("0"))
    values.append((ordered[-1][0], Decimal("100") - used))
    return values


class Importer:
    def __init__(self, dataset: dict, checksum: str, *, student_limit: int | None = None):
        self.dataset = dataset
        self.checksum = checksum
        self.student_limit = student_limit
        self.models = {
            name: apps.get_model(app_label, model)
            for name, app_label, model in (
                ("curriculum", "curriculum", "CurriculumVersion"),
                ("outcome", "curriculum", "Outcome"),
                ("course", "curriculum", "Course"),
                ("edge", "curriculum", "CurriculumEdge"),
                ("snapshot", "assessment", "AttainmentSnapshot"),
                ("instrument", "assessment", "AssessmentInstrument"),
                ("rubric", "assessment", "Rubric"),
                ("criterion", "assessment", "RubricCriterion"),
                ("level", "assessment", "PerformanceLevel"),
                ("item", "assessment", "AssessmentItem"),
                ("offering", "learning", "CourseOffering"),
                ("rps", "learning", "RPSVersion"),
                ("course_outcome", "learning", "CourseOutcome"),
                ("sub_outcome", "learning", "SubOutcome"),
                ("indicator", "learning", "PerformanceIndicator"),
                ("weekly_plan", "learning", "WeeklyPlan"),
                ("student", "academic_lifecycle", "StudentProfile"),
                ("status", "academic_lifecycle", "AcademicStatus"),
                ("plan", "academic_lifecycle", "EnrollmentPlan"),
                ("result", "academic_lifecycle", "AcademicResult"),
                ("task", "academic_lifecycle", "TaskInstance"),
                ("rule", "shared", "AcademicRule"),
                ("rule_package", "shared", "CohortRulePackage"),
            )
        }
        self.users = ensure_demo_assignments()
        self.counts: dict[str, int] = defaultdict(int)
        self.source_counts = source_inventory(dataset)
        self.skipped: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    def run(self) -> dict[str, int]:
        self.import_academic_governance()
        curriculum = self.import_curriculum()
        courses = self.import_courses(curriculum)
        self.import_edges(curriculum)
        self.import_learning_assessment(curriculum, courses)
        self.import_attainment(courses)
        self.import_students(curriculum, courses)
        self.import_tasks(curriculum)
        return dict(self.counts)

    def record_skip(self, category: str, reason: str, count: int = 1) -> None:
        if count:
            self.skipped[category][reason] += count

    def reconciliation(self) -> dict:
        skipped = {category: dict(reasons) for category, reasons in self.skipped.items()}
        for source_key, imported_key in RECONCILIATION_COVERAGE.items():
            source_count = self.source_counts.get(source_key, 0)
            imported_count = self.counts.get(imported_key, 0) if imported_key else 0
            already_skipped = sum(skipped.get(source_key, {}).values())
            gap = source_count - imported_count - already_skipped
            if gap > 0:
                skipped.setdefault(source_key, {})["not_in_current_import_scope"] = gap
        return {
            "contract": "obe-v5-import-reconciliation/1",
            "schema_version": self.dataset["schemaVersion"],
            "source_checksum": self.checksum,
            "student_limit": self.student_limit,
            "source": dict(sorted(self.source_counts.items())),
            "imported": dict(sorted(self.counts.items())),
            "skipped": {
                category: dict(sorted(reasons.items()))
                for category, reasons in sorted(skipped.items())
            },
            "errors": [],
        }

    def import_academic_governance(self) -> None:
        registry = self.dataset.get("academicRuleRegistry") or sample_rule_registry()
        Package = self.models["rule_package"]
        Rule = self.models["rule"]
        activated_at = timezone.make_aware(datetime(2024, 8, 1))
        for item in registry.get("rulePackages", []):
            code = item.get("code") or item["id"].rsplit("-V", 1)[0]
            Package.objects.update_or_create(
                code=code,
                version=item.get("version", 1),
                defaults={
                    "cohort_from": item["cohortFrom"],
                    "cohort_to": item.get("cohortTo"),
                    "effective_from": parse_date(item.get("effectiveFrom")),
                    "effective_to": parse_date(item.get("effectiveTo")),
                    "status": item.get("status", "active"),
                    "grade_scheme": item["gradeScheme"],
                    "minimum_passing_grade": item.get("minimumPassingGrade", "C"),
                    "minimum_thesis_grade": item.get("minimumThesisGrade", "B"),
                    "irs_policy": item.get("irsPolicy", {}),
                    "progress_milestones": item.get("progressMilestones", []),
                    "graduation_policy": {
                        "minimumTotalCredits": 144,
                        "minimumRequiredCredits": 126,
                        "minimumElectiveCredits": 18,
                        "englishScore": 400,
                    },
                    "created_by": self.users["prodi"],
                    "activated_by": self.users["gpm"],
                    "activated_at": activated_at,
                },
            )
            self.counts["rule_packages"] += 1
        for item in registry.get("rules", []):
            expression = item["expression"]
            Rule.objects.update_or_create(
                code=item["code"],
                version=item.get("version", 1),
                defaults={
                    "scope": {"type": item["scope"]},
                    "input_schema": {"required": sorted(expression)},
                    "expression": expression,
                    "priority": item.get("priority", 100),
                    "severity": item.get("severity", "blocking"),
                    "cohort": item.get("cohort", ""),
                    "effective_from": parse_date(item.get("effectiveFrom")),
                    "effective_to": parse_date(item.get("effectiveTo")),
                    "status": item.get("status", "active"),
                    "created_by": self.users["prodi"],
                    "reviewed_by": self.users["gpm"],
                    "activated_by": self.users["gpm"],
                    "review_note": "Imported from synthetic OBE schema v5",
                    "activated_at": activated_at,
                },
            )
            self.counts["academic_rules"] += 1

    def import_curriculum(self):
        CurriculumVersion = self.models["curriculum"]
        Outcome = self.models["outcome"]
        program = self.dataset["program"]
        metadata = self.dataset.get("importMetadata", {})
        activation_valid = program.get("creditPolicy", {}).get("activationValid", False)
        bk_weights = dict(
            proportional_allocations(
                [
                    (
                        item["id"],
                        sum(
                            (decimal(value) for value in item["cplDepth"].values()),
                            Decimal("0"),
                        ),
                    )
                    for item in self.dataset["knowledgeAreas"]
                ]
            )
        )
        curriculum, _ = CurriculumVersion.objects.update_or_create(
            program_code=program["id"],
            version=1,
            defaults={
                "public_id": uuid.UUID(program["uuid"]),
                "program_name": program["program"],
                "degree_level": program.get("degree", "sarjana"),
                "name": f"Kurikulum {program['program']} {program['curriculumYear']}",
                "curriculum_year": program["curriculumYear"],
                "cohort_from": program["curriculumYear"],
                "status": "draft" if activation_valid else "review",
                "checksum": "",
                "source_checksum": self.checksum,
                "effective_from": parse_date("2024-08-01"),
                "created_by_actor_id": str(self.users["prodi"].pk),
                "updated_by_actor_id": str(self.users["prodi"].pk),
                "approval_snapshot": {
                    "source_schema": self.dataset["schemaVersion"],
                    "source_file": self.dataset.get("source", {}).get("originalFileName"),
                    "source_sha256": self.checksum,
                    "dataset_snapshot": self.dataset.get("meta", {}).get("datasetSnapshot"),
                    "credit_policy": program.get("creditPolicy", {}),
                    "import_metadata": metadata,
                },
            },
        )
        legacy_versions = CurriculumVersion.objects.filter(
            program_code="IF",
            version=1,
            name="Kurikulum Informatika OBE",
            approval_snapshot={},
        ).exclude(pk=curriculum.pk)
        for legacy in legacy_versions:
            legacy.status = "archived"
            legacy.archive_reason = "Digantikan oleh paket kurikulum v5"
            legacy.save(update_fields=["status", "archive_reason", "updated_at"])
        self.counts["curricula"] += 1
        groups = (
            ("graduateProfiles", "PL"),
            ("cpl", "CPL"),
            ("knowledgeAreas", "BK"),
            ("cpmk", "CPMK"),
        )
        for key, kind in groups:
            for item in self.dataset[key]:
                Outcome.objects.update_or_create(
                    curriculum=curriculum,
                    kind=kind,
                    code=item["id"],
                    version=1,
                    defaults={
                        "public_id": uuid.UUID(item["uuid"]),
                        "name": item.get("name") or item["id"],
                        "description": item.get("description") or item.get("name") or item["id"],
                        "category": item.get("category", ""),
                        "depth": item.get("knowledgeDepth"),
                        "knowledge_depth": item.get("knowledgeDepth"),
                        "skill_depth": item.get("skillDepth"),
                        "attitude_depth": item.get("attitudeDepth"),
                        "owner_role": item.get("ownerRole", ""),
                        "weight": (
                            bk_weights[item["id"]] if kind == "BK" else decimal(item.get("weight"))
                        ),
                        "target": decimal(item.get("target"), "75"),
                        "status": "active",
                        "effective_from": parse_date(item.get("effectiveFrom")),
                        "effective_to": parse_date(item.get("effectiveTo")),
                    },
                )
                self.counts[kind.lower()] += 1
        return curriculum

    def import_courses(self, curriculum) -> dict[str, Any]:
        Course = self.models["course"]
        courses = {}
        for item in self.dataset["courses"]:
            course, _ = Course.objects.update_or_create(
                curriculum=curriculum,
                code=item["code"],
                version=1,
                defaults={
                    "public_id": uuid.UUID(item["uuid"]),
                    "name": item["name"],
                    "credits": item["sks"],
                    "required": item["status"].lower() == "wajib",
                    "recommended_semester": item["semester"],
                    "term": {"ganjil": "odd", "genap": "even"}.get(
                        item.get("offering", "").lower(), "both"
                    ),
                    "prerequisites": item.get("prerequisiteCourseCodes", []),
                    "equivalence_codes": item.get("equivalenceCourseCodes", []),
                    "capacity": item.get("capacityDefault", 40),
                    "status": "active",
                    "effective_from": parse_date(item.get("effectiveFrom")),
                    "effective_to": parse_date(item.get("effectiveTo")),
                },
            )
            courses[item["code"]] = course
            self.counts["courses"] += 1
        return courses

    def _learning_slice(self) -> tuple[dict, list[dict], list[dict], list[dict], list[dict], dict]:
        """Return the exact MIK1624101 slice, with a compact-fixture fallback."""
        learning = self.dataset.get("learning", {})
        rps_rows = learning.get("rpsVersions", [])
        rps = next(
            (row for row in rps_rows if row.get("courseCode") == "MIK1624101"),
            {
                "id": "RPS-MIK1624101-2024-V1",
                "uuid": "17237222-a7e1-5fa0-a42d-575473157ba6",
                "courseCode": "MIK1624101",
                "curriculumVersionId": "CURR-S1IF-2024-V1",
                "version": 1,
                "status": "published-demo",
                "publicationScope": "fixture-only",
                "effectiveAcademicYear": "2024/2025",
            },
        )
        outcomes = [
            row
            for row in learning.get("courseOutcomes", [])
            if row.get("rpsVersionId") == rps["id"]
        ] or [
            {
                "id": "CO-MIK1624101-01",
                "uuid": "7064abc5-ede5-522e-a6cd-80c9c6db0232",
                "localCode": "CPMK-01",
                "programCpmkId": "CPMK14",
                "description": "Mampu menerapkan konsep sistem untuk merancang solusi atas permasalahan sederhana.",
                "bloomLevel": "apply-analyze",
                "weight": 100,
                "target": 75,
            }
        ]
        outcome_ids = {row["id"] for row in outcomes}
        subs = [
            row
            for row in learning.get("subOutcomes", [])
            if row.get("courseOutcomeId") in outcome_ids
        ] or [
            {
                "id": f"SCO-CO-MIK1624101-01-0{order}",
                "uuid": uid,
                "courseOutcomeId": "CO-MIK1624101-01",
                "code": f"CPMK-01.0{order}",
                "description": description,
                "weightWithinCourseOutcome": weight,
                "bloomLevel": bloom,
                "target": 75,
                "order": order,
            }
            for order, uid, description, weight, bloom in (
                (
                    1,
                    "864c0d92-29b0-5a7d-a343-e5e74776493e",
                    "Menjelaskan konsep utama Dasar Sistem secara tepat.",
                    30,
                    "understand",
                ),
                (
                    2,
                    "69b54200-f8ff-5073-8b6a-b9724613b87d",
                    "Menerapkan konsep dan kakas Dasar Sistem untuk menyelesaikan masalah terstruktur.",
                    40,
                    "apply",
                ),
                (
                    3,
                    "7048bb8e-d467-54e8-92a7-583b86c0f3b3",
                    "Mengevaluasi hasil, keterbatasan, dan bukti pekerjaan pada Dasar Sistem.",
                    30,
                    "evaluate",
                ),
            )
        ]
        sub_ids = {row["id"] for row in subs}
        indicators = [
            row for row in learning.get("indicators", []) if row.get("subOutcomeId") in sub_ids
        ]
        if not indicators:
            indicator_uuids = (
                "7a2126db-4cb0-5e86-bffb-cce8def2678b",
                "f0fca361-f0ff-5095-a408-4881289fd323",
                "825a982f-c26c-5aaa-9937-b7561fff74a7",
            )
            indicators = [
                {
                    "id": f"IND-{sub['id']}",
                    "uuid": uid,
                    "subOutcomeId": sub["id"],
                    "description": f"Mahasiswa menghasilkan respons atau artefak terukur untuk: {sub['description']}",
                    "measurementUnit": "normalized-score-0-100",
                    "target": 75,
                    "observable": True,
                }
                for sub, uid in zip(subs, indicator_uuids, strict=True)
            ]
        weeks = [
            row for row in learning.get("weeklyPlans", []) if row.get("rpsVersionId") == rps["id"]
        ]
        if not weeks:
            weeks = []
            regular_index = 0
            for week in range(1, 17):
                if week in {8, 16}:
                    sub_indexes = [0] if week == 8 else [1, 2]
                    weeks.append(
                        {
                            "week": week,
                            "subOutcomeIds": [subs[index]["id"] for index in sub_indexes],
                            "indicatorIds": [],
                            "topic": "Ujian Tengah Semester"
                            if week == 8
                            else "Ujian Akhir Semester",
                            "methods": ["assessment"],
                            "activities": ["midterm-exam" if week == 8 else "final-exam"],
                            "contactMinutes": 90,
                            "structuredMinutes": 0,
                            "independentMinutes": 0,
                        }
                    )
                    continue
                sub = subs[regular_index % 3]
                indicator = indicators[regular_index % 3]
                regular_index += 1
                methods = (
                    ["case-based-learning", "discussion"]
                    if regular_index % 2
                    else ["problem-based-learning", "collaborative-learning"]
                )
                weeks.append(
                    {
                        "week": week,
                        "subOutcomeIds": [sub["id"]],
                        "indicatorIds": [indicator["id"]],
                        "topic": f"Dasar Sistem: pembelajaran tahap {regular_index}",
                        "methods": methods,
                        "activities": ["instruction", "guided-practice", "reflection"],
                        "contactMinutes": 150,
                        "structuredMinutes": 180,
                        "independentMinutes": 180,
                    }
                )
        assessment = self.dataset.get("assessment", {})
        return rps, outcomes, subs, indicators, weeks, assessment

    def import_learning_assessment(self, curriculum, courses: dict[str, Any]) -> None:
        rps_data, outcomes, subs, indicators, weeks, assessment = self._learning_slice()
        course = courses[rps_data["courseCode"]]
        Offering = self.models["offering"]
        RPS = self.models["rps"]
        CourseOutcome = self.models["course_outcome"]
        SubOutcome = self.models["sub_outcome"]
        Indicator = self.models["indicator"]
        WeeklyPlan = self.models["weekly_plan"]
        Instrument = self.models["instrument"]
        Rubric = self.models["rubric"]
        Criterion = self.models["criterion"]
        Level = self.models["level"]
        Item = self.models["item"]
        offering, _ = Offering.objects.update_or_create(
            course_public_id=course.public_id,
            academic_year="2024/2025",
            semester="odd",
            class_code="A",
            defaults={
                "public_id": uuid.UUID("6e014092-3290-57cb-9b40-b58dc88b97e2"),
                "curriculum_version_public_id": curriculum.public_id,
                "parallel_group": "PG-2024-1-MIK1624101",
                "coordinator": self.users["pengampu"],
                "schedule": {"day": "Rabu", "startTime": "13:00", "durationMinutes": 150},
                "room": "FSM-334",
                "capacity": 50,
                "status": "completed-demo",
                "starts_on": date(2024, 8, 1),
                "ends_on": date(2024, 12, 31),
            },
        )
        offering.lecturers.add(self.users["pengampu"])
        rps, _ = RPS.objects.update_or_create(
            offering=offering,
            version=rps_data.get("version", 1),
            defaults={
                "public_id": uuid.UUID(rps_data["uuid"]),
                "status": "draft",
                "content": {
                    "references": ["Spesifikasi OBE schema v5"],
                    "learning_materials": ["Dasar Sistem"],
                    "source_status": rps_data.get("status"),
                    "publication_scope": rps_data.get("publicationScope", "fixture-only"),
                    "source_ref": rps_data.get("sourceRef", {"recordKey": rps_data["id"]}),
                },
                "total_assessment_weight": decimal(rps_data.get("assessmentWeightTotal"), "100"),
                "authored_by": self.users["pengampu"],
                "effective_from": date(2024, 8, 1),
                "created_by_actor_id": str(self.users["pengampu"].pk),
                "updated_by_actor_id": str(self.users["pengampu"].pk),
            },
        )
        outcome_map = {}
        for order, row in enumerate(outcomes, 1):
            program_cpmk = row["programCpmkId"]
            cpl_ids = [
                cpl_id
                for cpl_id, cpmk_ids in self.dataset["cplToCpmk"].items()
                if program_cpmk in cpmk_ids
            ]
            obj, _ = CourseOutcome.objects.update_or_create(
                rps=rps,
                code=row["localCode"],
                defaults={
                    "public_id": uuid.UUID(row["uuid"]),
                    "description": row["description"],
                    "bloom_level": row["bloomLevel"],
                    "target": decimal(row.get("target"), "75"),
                    "weight": decimal(row["weight"]),
                    "order": order,
                    "program_cpmk_ids": [program_cpmk],
                    "cpl_ids": cpl_ids,
                    "status": "active",
                },
            )
            outcome_map[row["id"]] = obj
            self.counts["rps_course_outcomes"] += 1
        sub_map = {}
        for row in subs:
            obj, _ = SubOutcome.objects.update_or_create(
                rps=rps,
                code=row["code"],
                defaults={
                    "public_id": uuid.UUID(row["uuid"]),
                    "course_outcome": outcome_map[row["courseOutcomeId"]],
                    "description": row["description"],
                    "bloom_level": row["bloomLevel"],
                    "target": decimal(row.get("target"), "75"),
                    "weight": decimal(row["weightWithinCourseOutcome"]),
                    "order": row.get("order", 1),
                    "status": "active",
                },
            )
            sub_map[row["id"]] = obj
            self.counts["rps_sub_outcomes"] += 1
        indicator_map = {}
        for order, row in enumerate(indicators, 1):
            obj, _ = Indicator.objects.update_or_create(
                rps=rps,
                code=row["id"],
                defaults={
                    "public_id": uuid.UUID(row["uuid"]),
                    "sub_outcome": sub_map[row["subOutcomeId"]],
                    "description": row["description"],
                    "measurement": row.get("measurementUnit", "normalized-score-0-100"),
                    "target": decimal(row.get("target"), "75"),
                    "observable": row.get("observable", True),
                    "order": order,
                    "status": "active",
                },
            )
            indicator_map[row["id"]] = obj
            self.counts["rps_indicators"] += 1
        for row in weeks:
            week = int(row["week"])
            meeting_type = "midterm" if week == 8 else "final" if week == 16 else "regular"
            WeeklyPlan.objects.update_or_create(
                rps=rps,
                week=week,
                defaults={
                    "meeting_type": meeting_type,
                    "outcomes": [sub_map[item].code for item in row.get("subOutcomeIds", [])],
                    "indicators": [
                        indicator_map[item].code for item in row.get("indicatorIds", [])
                    ],
                    "material": row["topic"],
                    "methods": row["methods"],
                    "activities": row["activities"],
                    "contact_minutes": row["contactMinutes"],
                    "structured_minutes": row["structuredMinutes"],
                    "independent_minutes": row["independentMinutes"],
                    "planned_date": date(2024, 8, 1) + timedelta(days=(week - 1) * 7),
                },
            )
            self.counts["weekly_plans"] += 1

        rubric_rows = assessment.get("rubricLibrary") or [
            {
                "id": "RUBRIC-ANALYTIC-4LEVEL-V1",
                "uuid": "fbd7cf5d-0948-51da-a561-3163988597df",
                "version": 1,
                "type": "analytic",
                "criteria": [
                    {"code": "ACCURACY", "name": "Ketepatan", "weight": 35},
                    {"code": "METHOD", "name": "Metode dan Penalaran", "weight": 30},
                    {"code": "COMPLETENESS", "name": "Kelengkapan", "weight": 20},
                    {"code": "COMMUNICATION", "name": "Komunikasi dan Dokumentasi", "weight": 15},
                ],
                "levels": [
                    {"code": "L4", "name": "Istimewa", "min": 90, "max": 100},
                    {"code": "L3", "name": "Unggul", "min": 75, "max": 89.99},
                    {"code": "L2", "name": "Kompeten", "min": 60, "max": 74.99},
                    {"code": "L1", "name": "Belum Kompeten", "min": 0, "max": 59.99},
                ],
            },
            {
                "id": "RUBRIC-NUMERIC-MARKING-V1",
                "uuid": "4bbfdcf7-26b0-5a92-a7ff-373b048cab37",
                "version": 1,
                "type": "numeric-marking-scheme",
                "criteria": [{"code": "TOTAL", "name": "Skor Total", "weight": 100}],
                "levels": [],
            },
        ]
        rubric_map = {}
        indicator_codes = [item.code for item in indicator_map.values()]
        sub_codes = [item.code for item in sub_map.values()]
        for row in rubric_rows:
            rubric_code = row["id"].rsplit("-V", 1)[0]
            rubric = Rubric.objects.filter(code=rubric_code, version=row.get("version", 1)).first()
            if rubric is None:
                rubric = Rubric.objects.create(
                    code=rubric_code,
                    version=row.get("version", 1),
                    public_id=uuid.UUID(row["uuid"]),
                    title=row["id"],
                    kind="numeric" if row["type"] == "numeric-marking-scheme" else row["type"],
                    status="draft",
                )
            rubric_map[row["id"]] = rubric
            if rubric.status != "published":
                for order, criterion in enumerate(row["criteria"], 1):
                    Criterion.objects.update_or_create(
                        rubric=rubric,
                        code=criterion["code"],
                        defaults={
                            "title": criterion["name"],
                            "description": f"Kriteria {criterion['name']} untuk capaian Dasar Sistem",
                            "weight": decimal(criterion["weight"]),
                            "indicator_codes": indicator_codes,
                            "sub_outcome_codes": sub_codes,
                            "order": order,
                        },
                    )
                for order, level in enumerate(row.get("levels", []), 1):
                    Level.objects.update_or_create(
                        rubric=rubric,
                        code=level["code"],
                        defaults={
                            "descriptor": level["name"],
                            "minimum": decimal(level["min"]),
                            "maximum": decimal(level["max"]),
                            "points": decimal(level["min"]),
                            "order": order,
                        },
                    )
                rubric.status = "published"
                rubric.save(update_fields=["status", "updated_at"])
            self.counts["rubrics"] += 1

        plan_rows = [
            row
            for row in assessment.get("assessmentPlans", [])
            if row.get("rpsVersionId") == rps_data["id"]
        ]
        if not plan_rows:
            weights = {
                "PARTICIPATION": 10,
                "ASSIGNMENT": 20,
                "QUIZ": 10,
                "PRACTICE_PROJECT": 20,
                "MIDTERM": 20,
                "FINAL": 20,
            }
            names = {
                "PARTICIPATION": "Aktivitas Partisipatif",
                "ASSIGNMENT": "Tugas",
                "QUIZ": "Kuis",
                "PRACTICE_PROJECT": "Praktikum/Proyek/Presentasi",
                "MIDTERM": "Ujian Tengah Semester",
                "FINAL": "Ujian Akhir Semester",
            }
            plan_uuids = {
                "PARTICIPATION": "4dcb3d03-71f6-5aaf-a644-efede9ec97ba",
                "ASSIGNMENT": "9ad9feb3-5048-5ef7-99d7-0f0667eb00a6",
                "QUIZ": "a8bb7b72-bb42-56d0-9d54-db214f1183ea",
                "PRACTICE_PROJECT": "7265878b-baa1-5b28-9c7d-8abacf003f0b",
                "MIDTERM": "6e20e5ed-1259-582c-8591-bde00c597b60",
                "FINAL": "96cc0b47-0be7-5b44-95b1-2455f44b0928",
            }
            plan_rows = []
            for index, code in enumerate(weights):
                mapped = [subs[index % 3]] if index < 3 else subs
                plan_rows.append(
                    {
                        "id": f"ASM-MIK1624101-{code}",
                        "uuid": plan_uuids[code],
                        "instrumentCode": code,
                        "name": names[code],
                        "weight": weights[code],
                        "attemptLimit": 1,
                        "rubricId": "RUBRIC-NUMERIC-MARKING-V1"
                        if code in {"MIDTERM", "FINAL"}
                        else "RUBRIC-ANALYTIC-4LEVEL-V1",
                        "outcomeMappings": [
                            {
                                "subOutcomeId": item["id"],
                                "allocationWeight": 100
                                if len(mapped) == 1
                                else [33.33, 33.33, 33.34][position],
                            }
                            for position, item in enumerate(mapped)
                        ],
                        "evidenceRequired": True,
                        "evidenceClass": "restricted-exam"
                        if code in {"MIDTERM", "FINAL"}
                        else "confidential",
                    }
                )
        instruments = []
        for index, row in enumerate(plan_rows, 1):
            mappings = []
            for mapping in row["outcomeMappings"]:
                sub = sub_map[mapping["subOutcomeId"]]
                mappings.append(
                    {
                        "sub_outcome_codes": [sub.code],
                        "indicator_codes": list(sub.indicators.values_list("code", flat=True)),
                        "allocation_weight": mapping["allocationWeight"],
                    }
                )
            rubric = rubric_map[row["rubricId"]]
            instrument, _ = Instrument.objects.update_or_create(
                offering_public_id=offering.public_id,
                code=row["instrumentCode"],
                version=1,
                defaults={
                    "public_id": uuid.UUID(row["uuid"]),
                    "rps_public_id": rps.public_id,
                    "title": row["name"],
                    "kind": "summative"
                    if row["instrumentCode"] in {"MIDTERM", "FINAL"}
                    else "formative",
                    "purpose": f"Mengukur capaian melalui {row['name']}",
                    "participant_scope": {"offering": str(offering.public_id)},
                    "mode": "onsite",
                    "weight": decimal(row["weight"]),
                    "schedule": timezone.make_aware(
                        datetime(2024, 8, 1) + timedelta(days=index * 14)
                    ),
                    "attempts": row.get("attemptLimit", 1),
                    "assessor_id": str(self.users["pengampu"].pk),
                    "mappings": mappings,
                    "blueprint": {
                        "outcome_distribution": mappings,
                        "difficulty": "mixed",
                        "form": "constructed-response",
                        "coverage": mappings,
                        "durationMinutes": 90,
                    },
                    "rubric_public_id": rubric.public_id,
                    "evidence_required": row.get("evidenceRequired", True),
                    "evidence_class": row.get("evidenceClass", "confidential"),
                    "status": "draft",
                },
            )
            Item.objects.update_or_create(
                instrument=instrument,
                code="ITEM-01",
                defaults={
                    "prompt": f"Tunjukkan bukti capaian untuk {row['name']}",
                    "item_type": "constructed-response",
                    "points": 100,
                    "difficulty": "mixed",
                    "indicator_codes": sorted(
                        {code for item in mappings for code in item["indicator_codes"]}
                    ),
                    "sub_outcome_codes": sorted(
                        {code for item in mappings for code in item["sub_outcome_codes"]}
                    ),
                    "answer_key": {"classification": "controlled", "reference": f"KEY-{row['id']}"},
                },
            )
            instruments.append(instrument)
            self.counts["assessment_instruments"] += 1
        snapshot = [
            {
                "code": row.code,
                "weight": str(row.weight),
                "mappings": row.mappings,
                "status": "published",
                "published_before_teaching": True,
                "source_status": "published-demo",
            }
            for row in sorted(instruments, key=lambda item: item.code)
        ]
        rps.content = {**rps.content, "assessment_snapshot": snapshot}
        rps.save(update_fields=["content", "updated_at"])
        self.counts["course_offerings"] += 1
        self.counts["rps_versions"] += 1

    def import_edges(self, curriculum) -> None:
        groups: dict[tuple[str, str, str], list[tuple[str, Decimal]]] = defaultdict(list)
        cpmk_weights = {
            item["id"]: decimal(item.get("weight"), "1") for item in self.dataset["cpmk"]
        }
        for cpl in self.dataset["cpl"]:
            for pl_id in cpl.get("plIds", []):
                groups[("PL", pl_id, "CPL")].append((cpl["id"], decimal(cpl.get("weight"), "1")))
        for area in self.dataset["knowledgeAreas"]:
            for cpl_id, depth in area.get("cplDepth", {}).items():
                groups[("CPL", cpl_id, "BK")].append((area["id"], decimal(depth, "1")))
        for cpl_id, cpmk_ids in self.dataset["cplToCpmk"].items():
            groups[("CPL", cpl_id, "CPMK")].extend(
                (cpmk_id, cpmk_weights[cpmk_id]) for cpmk_id in cpmk_ids
            )
        for course in self.dataset["courses"]:
            for cpmk_id in course.get("cpmkIds", []):
                groups[("COURSE", course["code"], "CPMK")].append((cpmk_id, cpmk_weights[cpmk_id]))
            for area_id in course.get("knowledgeAreaIds", []):
                groups[("BK", area_id, "COURSE")].append(
                    (course["code"], decimal(course.get("sks"), "1"))
                )
        Edge = self.models["edge"]
        desired_pks = []
        for (source_type, source_id, target_type), targets in groups.items():
            for target_id, weight in proportional_allocations(targets):
                edge, _ = Edge.objects.update_or_create(
                    curriculum=curriculum,
                    source_type=source_type,
                    source_id=source_id,
                    target_type=target_type,
                    target_id=target_id,
                    version=1,
                    defaults={
                        "public_id": stable_uuid(
                            "edge", source_type, source_id, target_type, target_id
                        ),
                        "allocation_weight": weight,
                        "allocation_method": "derived-proportional",
                        "approval_reference": "",
                        "is_unallocated": False,
                        "status": "active",
                        "effective_from": curriculum.effective_from,
                    },
                )
                desired_pks.append(edge.pk)
                self.counts["edges"] += 1
        Edge.objects.filter(curriculum=curriculum).exclude(pk__in=desired_pks).delete()

    def import_attainment(self, courses: dict[str, Any]) -> None:
        Snapshot = self.models["snapshot"]
        program_id = self.dataset["program"]["id"]
        program_values: dict[str, list[tuple[Decimal, int, str]]] = defaultdict(list)
        for item in self.dataset["courses"]:
            actual = item.get("attainment")
            if actual is None:
                continue
            denominator = int(item.get("attainmentDenominator") or 0)
            target = decimal(item.get("targetAttainment"), "75")
            for cpl_id in item.get("cplIds", []):
                Snapshot.objects.update_or_create(
                    id=stable_uuid("attainment", "course", item["code"], cpl_id),
                    defaults={
                        "scope_type": "course",
                        "scope_id": item["code"],
                        "outcome_code": cpl_id,
                        "actual": decimal(actual),
                        "target": target,
                        "denominator": denominator,
                        "coverage": Decimal("100") if denominator else Decimal("0"),
                        "formula_version": "sample-v5/course-attainment",
                        "source_versions": {
                            "schema": self.dataset["schemaVersion"],
                            "course": str(courses[item["code"]].public_id),
                            "source": item.get("attainmentSource"),
                        },
                        "trace": [item["code"]],
                        "blocking_reasons": [],
                    },
                )
                program_values[cpl_id].append((decimal(actual), denominator, item["code"]))
                self.counts["course_attainment"] += 1
        for cpl_id, values in program_values.items():
            denominator = sum(value[1] for value in values)
            if denominator:
                program_actual = (
                    sum((value * count for value, count, _ in values), Decimal("0")) / denominator
                )
            else:
                program_actual = sum((value for value, _, _ in values), Decimal("0")) / len(values)
            Snapshot.objects.update_or_create(
                id=stable_uuid("attainment", "program", program_id, cpl_id),
                defaults={
                    "scope_type": "program",
                    "scope_id": program_id,
                    "outcome_code": cpl_id,
                    "actual": program_actual.quantize(Decimal("0.01")),
                    "target": Decimal("75"),
                    "denominator": denominator,
                    "coverage": Decimal("100") if denominator else Decimal("0"),
                    "formula_version": "sample-v5/program-course-weighted",
                    "source_versions": {"schema": self.dataset["schemaVersion"]},
                    "trace": [code for _, _, code in values],
                    "blocking_reasons": [],
                },
            )
            self.counts["program_attainment"] += 1

    def import_students(self, curriculum, courses: dict[str, Any]) -> None:
        StudentProfile = self.models["student"]
        AcademicStatus = self.models["status"]
        EnrollmentPlan = self.models["plan"]
        AcademicResult = self.models["result"]
        User = apps.get_model(settings.AUTH_USER_MODEL)
        all_students = self.dataset.get("students", [])
        students = all_students
        if self.student_limit is not None:
            students = students[: self.student_limit]
            self.record_skip("students", "student_limit", len(all_students) - len(students))
        for index, item in enumerate(students):
            if index == 0:
                user = self.users["mahasiswa"]
                user.first_name = item["name"][:150]
                user.save(update_fields=["first_name"])
            else:
                username = f"sample-{item['nim']}"
                user, created = User.objects.get_or_create(
                    username=username,
                    defaults={"first_name": item["name"][:150], "is_active": False},
                )
                if created:
                    user.set_unusable_password()
                    user.save(update_fields=["password"])
            curriculum_reference = item.get("curriculumVersionId")
            curriculum_public_id = (
                curriculum.public_id
                if curriculum_reference == "CURR-S1IF-2024-V1"
                else stable_uuid("curriculum-reference", curriculum_reference)
            )
            student, _ = StudentProfile.objects.update_or_create(
                student_number=item["nim"],
                defaults={
                    "public_id": uuid.UUID(item["uuid"]),
                    "user": user,
                    "cohort": item["cohortYear"],
                    "curriculum_public_id": curriculum_public_id,
                    "rule_package": item.get("rulePackageId", "CURRENT-AABBC")[:32],
                },
            )
            self.counts["students"] += 1
            histories = item.get("academicStatusHistory") or [
                {"status": item["academicStatus"], "effectiveFrom": f"{item['cohortYear']}-08-01"}
            ]
            for history_index, history in enumerate(histories, 1):
                AcademicStatus.objects.update_or_create(
                    student=student,
                    effective_from=history.get("effectiveFrom"),
                    version=history_index,
                    defaults={
                        "public_id": stable_uuid(
                            "status", item["nim"], history_index, history.get("effectiveFrom")
                        ),
                        "effective_to": history.get("effectiveTo"),
                        "status": history["status"],
                        "reason": f"Imported from {history.get('source', 'sample-v5')}",
                        "approved_by": self.users["prodi"],
                        "documents": [],
                    },
                )
                self.counts["statuses"] += 1
            for semester in item.get("semesterRecords", []):
                enrollments = semester.get("courseEnrollments", [])
                course_ids = [
                    str(courses[enrollment["courseCode"]].public_id)
                    for enrollment in enrollments
                    if enrollment["courseCode"] in courses
                ]
                plan_id = semester.get("irs", {}).get("id") or semester.get("uuid")
                EnrollmentPlan.objects.update_or_create(
                    student=student,
                    academic_year=semester["academicYear"],
                    semester=semester["semesterNumber"],
                    version=1,
                    defaults={
                        "public_id": stable_uuid("plan", plan_id),
                        "course_public_ids": course_ids,
                        "total_credits": semester.get("semesterCredits", 0),
                        "decision_snapshot": semester.get("irs", {}),
                        "status": semester.get("irs", {}).get("status", "approved"),
                        "advisor_id": "DPA-DEMO",
                    },
                )
                self.counts["plans"] += 1
                for enrollment in enrollments:
                    status = enrollment_status(enrollment)
                    if status != "completed":
                        self.record_skip("academic_results", status)
                        continue
                    course = courses.get(enrollment["courseCode"])
                    if course is None:
                        self.record_skip("academic_results", "unknown_course")
                        continue
                    AcademicResult.objects.update_or_create(
                        student=student,
                        course_public_id=course.public_id,
                        attempt=enrollment.get("attemptNumber", 1),
                        defaults={
                            "public_id": uuid.UUID(enrollment["recordId"]),
                            "academic_year": semester["academicYear"],
                            "semester": semester["semesterNumber"],
                            "credits": enrollment["sks"],
                            "letter": enrollment["grade"],
                            "grade_point": decimal(enrollment.get("gradePoint")),
                            "passed": enrollment.get("passed", False),
                            "source_type": enrollment.get("source", "sample-v5")[:24],
                            "trace": {
                                "offering_id": enrollment.get("offeringId"),
                                "score": enrollment.get("score"),
                                "attendance": enrollment.get("attendance"),
                                "engagement": enrollment.get("engagement"),
                                "assessment_scores": enrollment.get("assessmentScores", {}),
                                "uas_eligibility": enrollment.get("uasEligibility"),
                            },
                        },
                    )
                    self.counts["results"] += 1

    def import_tasks(self, curriculum) -> None:
        Task = self.models["task"]
        tasks = (
            (
                "prodi",
                "review-credit-policy",
                "Tinjau anomali 129 SKS wajib",
                "curriculum",
                str(curriculum.public_id),
                1,
            ),
            (
                "gpm",
                "verify-program-attainment",
                "Verifikasi capaian CPL dataset v5",
                "attainment",
                self.dataset["program"]["id"],
                2,
            ),
            (
                "pengampu",
                "prepare-course-evidence",
                "Periksa pemetaan CPMK dan bukti asesmen",
                "course",
                self.dataset["courses"][0]["code"],
                3,
            ),
            (
                "mahasiswa",
                "review-academic-progress",
                "Periksa riwayat studi dan capaian pribadi",
                "student",
                self.dataset.get("students", [{}])[0].get("nim", "demo"),
                3,
            ),
        )
        for offset, (role, code, title, entity_type, entity_id, priority) in enumerate(tasks, 1):
            Task.objects.update_or_create(
                idempotency_key=f"sample-v5:{role}:{code}",
                defaults={
                    "public_id": stable_uuid("task", role, code),
                    "owner": self.users[role],
                    "code": code,
                    "title": title,
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "due_at": timezone.now() + timedelta(days=offset * 3),
                    "status": "not-started",
                    "priority": priority,
                    "required_evidence": [],
                },
            )
            self.counts["tasks"] += 1


class Command(BaseCommand):
    help = "Import dataset sintetis OBE schema v5 secara transaksional dan idempotent"

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            type=Path,
            default=DEFAULT_FIXTURE,
            help="Path JSON schema v5; default memakai fixture compact repository",
        )
        parser.add_argument(
            "--student-limit",
            type=int,
            default=None,
            help="Batasi jumlah mahasiswa yang diimpor; default mengimpor semua record pada file",
        )
        parser.add_argument(
            "--report",
            type=Path,
            default=None,
            help="Tulis laporan rekonsiliasi JSON source/imported/skipped/errors",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        path = options["path"]
        student_limit = options["student_limit"]
        report_path = options["report"]
        if student_limit is not None and student_limit < 0:
            raise CommandError("--student-limit tidak boleh negatif")
        try:
            dataset, checksum = load_dataset(path)
        except CommandError as exc:
            if report_path is not None:
                write_reconciliation(
                    report_path,
                    {
                        "contract": "obe-v5-import-reconciliation/1",
                        "schema_version": None,
                        "source_checksum": None,
                        "student_limit": student_limit,
                        "source": {},
                        "imported": {},
                        "skipped": {},
                        "errors": [str(exc)],
                    },
                )
            raise
        importer = Importer(dataset, checksum, student_limit=student_limit)
        try:
            counts = importer.run()
        except Exception as exc:
            if report_path is not None:
                reconciliation = importer.reconciliation()
                reconciliation["errors"] = [f"{type(exc).__name__}: {exc}"]
                write_reconciliation(report_path, reconciliation)
            raise
        reconciliation = importer.reconciliation()
        if report_path is not None:
            write_reconciliation(report_path, reconciliation)
        summary = ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))
        skipped = sum(
            count for reasons in reconciliation["skipped"].values() for count in reasons.values()
        )
        self.stdout.write(
            self.style.SUCCESS(f"Import OBE v5 selesai ({summary}; skipped={skipped})")
        )
