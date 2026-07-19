import hashlib
import json
import os
import uuid
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from obe.academic_lifecycle.models import (
    AcademicResult,
    AcademicStatus,
    EnrollmentPlan,
    LifecycleApplication,
    LifecycleConfiguration,
    StudentProfile,
)
from obe.ai.models import PromptTemplate
from obe.assessment.models import Score, Submission
from obe.curriculum.models import CurriculumVersion
from obe.evidence.models import EvidenceRecord
from obe.identity.models import LecturerProfile, RoleAssignment
from obe.integration.models import IdentifierAlias, IntegrationContract
from obe.quality.models import IntegrityIssue, QualityCycle, QualityFinding, QualityStandard
from obe.secure_exam.models import Exam
from obe.shared.models import (
    AuditEvent,
    CohortRulePackage,
    DecisionOverride,
    FeatureFlag,
    FileManifest,
)


@pytest.mark.django_db
def test_import_rejects_truncated_json_before_writing(tmp_path):
    source = tmp_path / "truncated.json"
    source.write_text('{"schemaVersion":"5.0.0","students":[{"nim":"1"}', encoding="utf-8")
    with pytest.raises(CommandError, match="bukan JSON lengkap"):
        call_command("import_obe_sample", path=source)


@pytest.mark.django_db
def test_import_skips_non_completed_enrollments_and_reports_reconciliation(
    settings, monkeypatch, tmp_path
):
    monkeypatch.setenv("OBE_DEMO_PASSWORD", f"runtime-{uuid.uuid4().hex}")
    dataset = json.loads(
        (settings.BASE_DIR / "fixtures/sample-data-2020-2026-obe-spec-v5.compact.json").read_text()
    )
    template = dataset["students"][0]["semesterRecords"][0]["courseEnrollments"][0]
    for status, record_id in (
        ("planned", "06e7c417-b050-5e93-9b3b-9ab412ce54fd"),
        ("upcoming", "833cc0d4-56bd-550e-a7fd-d59c5b34fe70"),
    ):
        enrollment = dict(template)
        enrollment.update(
            {
                "recordId": record_id,
                "status": status,
                "grade": None,
                "gradePoint": None,
                "passed": False,
            }
        )
        dataset["students"][0]["semesterRecords"][0]["courseEnrollments"].append(enrollment)
    source = tmp_path / "sample-with-planned.json"
    source.write_text(json.dumps(dataset), encoding="utf-8")
    report = tmp_path / "reconciliation.json"

    call_command("import_obe_sample", path=source, report=report)

    result = json.loads(report.read_text())
    assert AcademicResult.objects.count() == 212
    assert result["source"]["course_enrollments"] == 214
    assert result["imported"]["results"] == 212
    assert result["skipped"]["academic_results"] == {"planned": 1, "upcoming": 1}
    assert result["errors"] == []


@pytest.mark.django_db
def test_import_rejects_completed_enrollment_without_grade_before_writing(
    settings, monkeypatch, tmp_path
):
    monkeypatch.setenv("OBE_DEMO_PASSWORD", f"runtime-{uuid.uuid4().hex}")
    dataset = json.loads(
        (settings.BASE_DIR / "fixtures/sample-data-2020-2026-obe-spec-v5.compact.json").read_text()
    )
    enrollment = dataset["students"][0]["semesterRecords"][0]["courseEnrollments"][0]
    enrollment.update({"status": "completed", "grade": None})
    source = tmp_path / "sample-invalid-completed.json"
    source.write_text(json.dumps(dataset), encoding="utf-8")
    report = tmp_path / "invalid-reconciliation.json"

    with pytest.raises(CommandError, match="completed enrollment wajib memiliki grade"):
        call_command("import_obe_sample", path=source, report=report)

    assert CurriculumVersion.objects.count() == 0
    assert (
        "completed enrollment wajib memiliki grade" in json.loads(report.read_text())["errors"][0]
    )


@pytest.mark.django_db
def test_import_rejects_orphan_master_reference_before_writing(settings, monkeypatch, tmp_path):
    monkeypatch.setenv("OBE_DEMO_PASSWORD", f"runtime-{uuid.uuid4().hex}")
    dataset = json.loads(
        (settings.BASE_DIR / "fixtures/sample-data-2020-2026-obe-spec-v5.compact.json").read_text()
    )
    dataset["students"][0]["curriculumVersionId"] = "CURR-MISSING"
    source = tmp_path / "sample-orphan-master.json"
    source.write_text(json.dumps(dataset), encoding="utf-8")

    with pytest.raises(CommandError, match="curriculumVersionId tidak ditemukan"):
        call_command("import_obe_sample", path=source)

    assert CurriculumVersion.objects.count() == 0


@pytest.mark.django_db
def test_full_sample_imports_all_supported_records_idempotently(settings, tmp_path, monkeypatch):
    source = Path(
        os.environ.get("OBE_FULL_SAMPLE_PATH")
        or settings.BASE_DIR / "data/sample-data-2020-2026-obe-spec-v5.json"
    )
    monkeypatch.setenv("OBE_DEMO_PASSWORD", f"runtime-{uuid.uuid4().hex}")
    report = tmp_path / "full-reconciliation.json"
    call_command("import_obe_sample", path=source, report=report)
    first = json.loads(report.read_text())
    call_command("import_obe_sample", path=source, report=report)
    second = json.loads(report.read_text())
    dataset = json.loads(source.read_text())

    from obe.assessment.models import AssessmentInstrument, Rubric
    from obe.learning.models import CourseOffering, RPSVersion, WeeklyPlan
    from obe.learning.services import validate_rps

    rps = RPSVersion.objects.get(source_id="RPS-MIK1624101-2024-V1")
    assert WeeklyPlan.objects.filter(rps=rps).count() == 16
    assert AssessmentInstrument.objects.filter(rps_public_id=rps.public_id).count() == 6
    assert CourseOffering.objects.count() == len(dataset["courseOfferings"])
    assert RPSVersion.objects.count() == len(dataset["learning"]["rpsVersions"])
    assert WeeklyPlan.objects.count() == len(dataset["learning"]["weeklyPlans"])
    assert AssessmentInstrument.objects.count() == len(dataset["assessment"]["assessmentPlans"])
    assert Rubric.objects.count() == 2
    assert validate_rps(rps)["valid"]
    assert StudentProfile.objects.count() == 1597
    assert AcademicStatus.objects.count() == 1597
    assert AcademicStatus.objects.filter(status="admitted").count() == 218
    assert EnrollmentPlan.objects.count() == 12776
    assert AcademicResult.objects.count() == 56119
    curricula = {
        item.source_id: item for item in CurriculumVersion.objects.filter(source_id__isnull=False)
    }
    assert set(curricula) == {"CURR-LEGACY-DEMO-V1", "CURR-S1IF-2024-V1"}
    assert str(curricula["CURR-LEGACY-DEMO-V1"].public_id) == (
        "b69329c5-0f68-5832-84b5-75741b19dd04"
    )
    assert str(curricula["CURR-S1IF-2024-V1"].public_id) == ("80c134a5-abef-56fb-8549-dd8fd159ecc4")
    assert curricula["CURR-LEGACY-DEMO-V1"].status == "archived"
    assert curricula["CURR-S1IF-2024-V1"].status == "review"
    assert (
        StudentProfile.objects.filter(
            curriculum_public_id=curricula["CURR-LEGACY-DEMO-V1"].public_id
        ).count()
        == 899
    )
    assert (
        StudentProfile.objects.filter(
            curriculum_public_id=curricula["CURR-S1IF-2024-V1"].public_id
        ).count()
        == 698
    )
    assert not StudentProfile.objects.exclude(
        curriculum_public_id__in=[item.public_id for item in curricula.values()]
    ).exists()
    assert (
        StudentProfile.objects.filter(rule_package="LEGACY-ABCDE", rule_package_version=1).count()
        == 899
    )
    assert (
        StudentProfile.objects.filter(rule_package="CURRENT-AABBC", rule_package_version=1).count()
        == 698
    )
    packages = {item.code: item for item in CohortRulePackage.objects.filter(version=1)}
    assert packages["LEGACY-ABCDE"].grade_scheme == dataset["gradeScaleLegacy"]
    assert packages["CURRENT-AABBC"].grade_scheme == dataset["gradeScaleCurrent"]
    assert LecturerProfile.objects.count() == 43
    assert LecturerProfile.objects.get(lecturer_id="DSN018").user.username == "pengampu"
    assert RoleAssignment.objects.filter(source_id__isnull=False).count() == 36
    assert IdentifierAlias.objects.count() == 3851
    assert IdentifierAlias.objects.filter(namespace="course-code").count() == 1
    assert IdentifierAlias.objects.filter(namespace="course-offering").count() == 3850
    assert first["source"]["course_enrollments"] == 84641
    assert first["imported"]["results"] == 56119
    assert first["imported"]["curricula"] == 2
    assert first["imported"]["grade_scale_rows"] == 12
    assert first["imported"]["lecturers"] == 43
    assert first["imported"]["scoped_assignments"] == 36
    assert first["imported"]["identifier_aliases"] == 3851
    assert first["imported"]["course_offerings"] == 3850
    assert first["imported"]["rps_versions"] == 77
    assert first["imported"]["weekly_plans"] == 1232
    assert first["imported"]["assessment_instruments"] == 459
    assert FileManifest.objects.filter(source_id__isnull=False).count() == 366
    assert EvidenceRecord.objects.filter(source_id__isnull=False).count() == 366
    assert (
        EvidenceRecord.objects.filter(
            source_id__isnull=False, status="submitted", source_status="verified"
        ).count()
        == 366
    )
    assert Submission.objects.filter(source_id__isnull=False).count() == 366
    assert Score.objects.filter(source_id__isnull=False).count() == 366
    assert (
        DecisionOverride.objects.filter(
            source_id__isnull=False, status="reviewed", source_status="approved-demo"
        ).count()
        == 3330
    )
    assert FeatureFlag.objects.filter(source_id__isnull=False, state="disabled").count() == 10
    assert AuditEvent.objects.filter(source_id__isnull=False).count() == 7
    assert IntegrityIssue.objects.filter(source_id__isnull=False).count() == 8
    assert QualityStandard.objects.count() == 12
    assert QualityFinding.objects.count() == 3
    assert QualityCycle.objects.filter(period="dataset-v5").count() == 1
    assert PromptTemplate.objects.filter(source_id__isnull=False, status="draft").count() == 4
    assert (
        Exam.objects.filter(
            source_id__isnull=False, status="draft", source_status="approved-demo"
        ).count()
        == 1
    )
    assert LifecycleApplication.objects.count() == 3
    assert LifecycleConfiguration.objects.count() == 1
    assert IntegrationContract.objects.count() == 5
    stage4_keys = (
        "evidence_manifests",
        "evidence_submissions",
        "evidence_scores",
        "decision_overrides",
        "feature_flags",
        "audit_events",
        "quality_issues",
        "provus_standards",
        "provus_findings",
        "quality_cycles",
        "ai_prompts",
        "secure_exams",
        "lifecycle_applications",
        "lifecycle_configurations",
        "integration_contracts",
    )
    for key in stage4_keys:
        assert first["source"][key] == first["imported"][key]
        assert key not in first["skipped"]
    assert first["skipped"]["academic_results"] == {"planned": 16404, "upcoming": 12118}
    assert second == first


def test_repository_full_dataset_checksum_and_stage4_inventory(settings):
    from obe.integration.management.commands.import_obe_sample import source_inventory

    source = settings.BASE_DIR / "data/sample-data-2020-2026-obe-spec-v5.json"
    raw = source.read_bytes()
    assert len(raw) == 56_193_651
    assert hashlib.sha256(raw).hexdigest() == (
        "5d90915c2bbb46e9e44765299155c24782bccd2df75905c60c12e2391205aaa3"
    )
    inventory = source_inventory(json.loads(raw))
    assert {
        key: inventory[key]
        for key in (
            "evidence_manifests",
            "evidence_submissions",
            "evidence_scores",
            "decision_overrides",
            "feature_flags",
            "audit_events",
            "quality_issues",
            "provus_standards",
            "provus_findings",
            "ai_prompts",
            "secure_exams",
            "lifecycle_applications",
            "integration_contracts",
        )
    } == {
        "evidence_manifests": 366,
        "evidence_submissions": 366,
        "evidence_scores": 366,
        "decision_overrides": 3330,
        "feature_flags": 10,
        "audit_events": 7,
        "quality_issues": 8,
        "provus_standards": 12,
        "provus_findings": 3,
        "ai_prompts": 4,
        "secure_exams": 1,
        "lifecycle_applications": 3,
        "integration_contracts": 5,
    }
