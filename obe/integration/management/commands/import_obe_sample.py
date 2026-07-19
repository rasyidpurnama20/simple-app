import hashlib
import json
import uuid
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from obe.identity.services import ensure_demo_assignments

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


def stable_uuid(*parts: object) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, ":".join(str(part) for part in parts))


def parse_date(value):
    return value or None


def decimal(value, default="0") -> Decimal:
    return Decimal(str(default if value is None else value))


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
    return dataset, hashlib.sha256(raw).hexdigest()


def equal_allocations(targets: list[str]) -> list[tuple[str, Decimal]]:
    unique_targets = list(dict.fromkeys(targets))
    if not unique_targets:
        return []
    unit = (Decimal("100") / len(unique_targets)).quantize(Decimal("0.0001"))
    values = [(target, unit) for target in unique_targets[:-1]]
    used = unit * len(values)
    values.append((unique_targets[-1], Decimal("100") - used))
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
                ("student", "academic_lifecycle", "StudentProfile"),
                ("status", "academic_lifecycle", "AcademicStatus"),
                ("plan", "academic_lifecycle", "EnrollmentPlan"),
                ("result", "academic_lifecycle", "AcademicResult"),
                ("task", "academic_lifecycle", "TaskInstance"),
            )
        }
        self.users = ensure_demo_assignments()
        self.counts: dict[str, int] = defaultdict(int)

    def run(self) -> dict[str, int]:
        curriculum = self.import_curriculum()
        courses = self.import_courses(curriculum)
        self.import_edges(curriculum)
        self.import_attainment(courses)
        self.import_students(curriculum, courses)
        self.import_tasks(curriculum)
        return dict(self.counts)

    def import_curriculum(self):
        CurriculumVersion = self.models["curriculum"]
        Outcome = self.models["outcome"]
        program = self.dataset["program"]
        metadata = self.dataset.get("importMetadata", {})
        activation_valid = program.get("creditPolicy", {}).get("activationValid", False)
        curriculum, _ = CurriculumVersion.objects.update_or_create(
            program_code=program["id"],
            version=1,
            defaults={
                "public_id": uuid.UUID(program["uuid"]),
                "name": f"Kurikulum {program['program']} {program['curriculumYear']}",
                "cohort_from": program["curriculumYear"],
                "status": "draft" if activation_valid else "review",
                "checksum": self.checksum,
                "effective_from": "2024-08-01",
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
        CurriculumVersion.objects.filter(
            program_code="IF",
            version=1,
            name="Kurikulum Informatika OBE",
            approval_snapshot={},
        ).exclude(pk=curriculum.pk).update(status="archived")
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
                        "weight": decimal(item.get("weight")),
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
                    "capacity": item.get("capacityDefault", 40),
                    "status": "active",
                    "effective_from": parse_date(item.get("effectiveFrom")),
                    "effective_to": parse_date(item.get("effectiveTo")),
                },
            )
            courses[item["code"]] = course
            self.counts["courses"] += 1
        return courses

    def import_edges(self, curriculum) -> None:
        groups: dict[tuple[str, str, str], list[str]] = defaultdict(list)
        for cpl in self.dataset["cpl"]:
            for pl_id in cpl.get("plIds", []):
                groups[("PL", pl_id, "CPL")].append(cpl["id"])
        for cpl_id, cpmk_ids in self.dataset["cplToCpmk"].items():
            groups[("CPL", cpl_id, "CPMK")].extend(cpmk_ids)
        for course in self.dataset["courses"]:
            for cpmk_id in course.get("cpmkIds", []):
                groups[("CPMK", cpmk_id, "COURSE")].append(course["code"])
            for area_id in course.get("knowledgeAreaIds", []):
                groups[("BK", area_id, "COURSE")].append(course["code"])
        Edge = self.models["edge"]
        for (source_type, source_id, target_type), targets in groups.items():
            for target_id, weight in equal_allocations(targets):
                Edge.objects.update_or_create(
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
                        "status": "active",
                    },
                )
                self.counts["edges"] += 1

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
                    "formula_version": "sample-v5/program-weighted-course-attainment",
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
        students = self.dataset.get("students", [])
        if self.student_limit is not None:
            students = students[: self.student_limit]
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
                    course = courses.get(enrollment["courseCode"])
                    if course is None:
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
                            "letter": enrollment.get("grade", ""),
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

    @transaction.atomic
    def handle(self, *args, **options):
        path = options["path"]
        student_limit = options["student_limit"]
        if student_limit is not None and student_limit < 0:
            raise CommandError("--student-limit tidak boleh negatif")
        dataset, checksum = load_dataset(path)
        counts = Importer(dataset, checksum, student_limit=student_limit).run()
        summary = ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))
        self.stdout.write(self.style.SUCCESS(f"Import OBE v5 selesai ({summary})"))
