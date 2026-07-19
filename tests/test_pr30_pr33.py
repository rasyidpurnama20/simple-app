import json
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.utils import timezone

from obe.assessment.models import (
    AssessmentInstrument,
    CompetencyScale,
    ParallelExamPolicy,
    Submission,
    SubmissionGroup,
)
from obe.assessment.services import (
    analyze_parallel_results,
    approve_parallel_exam,
    approve_score_revision,
    best_attempt,
    create_question_set,
    finalize_submission,
    grade_submission,
    record_historical_score,
    release_question_set,
    reopen_submission,
    request_score_revision,
    requirement_met,
    review_parallel_exam,
    save_submission_draft,
    set_score_feedback,
)
from obe.evidence.models import EvidenceRecord
from obe.evidence.services import revise
from obe.learning.models import Attendance, CourseOffering, OfferingRoster
from obe.learning.services import (
    approve_exam_eligibility_override,
    evaluate_exam_eligibility,
    request_exam_eligibility_override,
)
from obe.shared.models import FileManifest


def actors():
    User = get_user_model()
    return tuple(
        User.objects.create_user(username=name)
        for name in ("pengampu-30", "gpm-30", "prodi-30", "student-30")
    )


def offering_and_instrument(owner, *, code="FINAL", deadline=None):
    offering = CourseOffering.objects.create(
        course_public_id=uuid.uuid4(),
        academic_year="2025/2026",
        semester="odd",
        class_code=str(uuid.uuid4())[:8],
        parallel_group="PG-IF-01",
        coordinator=owner,
        starts_on=date(2025, 8, 1),
        ends_on=date(2025, 12, 31),
    )
    instrument = AssessmentInstrument.objects.create(
        offering_public_id=offering.public_id,
        code=code,
        title=f"Instrumen {code}",
        kind="summative",
        purpose="Mengukur capaian utama",
        weight=100,
        schedule=timezone.now(),
        deadline_at=deadline,
        attempts=2,
        assessor_id=str(owner.pk),
        mappings=[
            {
                "sub_outcome_codes": ["CPMK-01.01"],
                "indicator_codes": ["IND-01"],
                "allocation_weight": 100,
            }
        ],
        blueprint={"coverage": ["IND-01"]},
        status="published",
        published_at=timezone.now(),
    )
    return offering, instrument


@pytest.mark.django_db
def test_pr30_parallel_exam_requires_equivalence_approval_and_flags_disparity():
    author, gpm, prodi, _ = actors()
    _, first = offering_and_instrument(author)
    _, second = offering_and_instrument(author)
    policy = ParallelExamPolicy(
        program_code="IF",
        strict_same_question=False,
        disparity_threshold=Decimal("10"),
        status="active",
        created_by=author,
        approved_by=prodi,
        approved_at=timezone.now(),
    )
    policy.full_clean()
    policy.save()
    first_set = create_question_set(
        instrument=first,
        parallel_group="PG-IF-01",
        code="UAS-A",
        questions=[{"id": 1, "prompt": "A"}],
        coverage={"IND-01": 100},
        difficulty={"medium": 100},
        authored_by=author,
    )
    second_set = create_question_set(
        instrument=second,
        parallel_group="PG-IF-01",
        code="UAS-B",
        questions=[{"id": 1, "prompt": "B"}],
        coverage={"IND-01": 100},
        difficulty={"medium": 100},
        authored_by=author,
    )
    strict_policy = ParallelExamPolicy(
        program_code="IF",
        version=2,
        strict_same_question=True,
        disparity_threshold=Decimal("10"),
        status="active",
        created_by=author,
        approved_by=prodi,
        approved_at=timezone.now(),
    )
    strict_policy.full_clean()
    strict_policy.save()
    with pytest.raises(ValidationError, match="strict-same-question"):
        review_parallel_exam(
            question_sets=[first_set, second_set],
            policy=strict_policy,
            reviewer=gpm,
            equivalence_report={
                "coverage_equivalent": True,
                "difficulty_equivalent": True,
            },
            difference_reason="Soal berbeda",
        )
    with pytest.raises(ValidationError, match="alasan"):
        review_parallel_exam(
            question_sets=[first_set, second_set],
            policy=policy,
            reviewer=gpm,
            equivalence_report={
                "coverage_equivalent": True,
                "difficulty_equivalent": True,
            },
        )
    review = review_parallel_exam(
        question_sets=[first_set, second_set],
        policy=policy,
        reviewer=gpm,
        equivalence_report={"coverage_equivalent": True, "difficulty_equivalent": True},
        difference_reason="Kasus berbeda, blueprint identik",
    )
    with pytest.raises(ValidationError, match="Reviewer"):
        approve_parallel_exam(review, user=gpm)
    review = approve_parallel_exam(review, user=prodi)
    first_set.refresh_from_db()
    release_question_set(first_set, review=review, user=prodi)
    result = analyze_parallel_results(review, class_scores={"A": [90, 80], "B": [60, 50]}, user=gpm)
    assert result == {
        "means": {"A": "85.00", "B": "55.00"},
        "disparity": "30.00",
        "threshold": "10.00",
        "flagged": True,
    }


@pytest.mark.django_db
def test_pr31_grade_normalization_history_best_attempt_and_requirements():
    assessor, _, _, student = actors()
    _, instrument = offering_and_instrument(assessor)
    submission = Submission.objects.create(
        instrument=instrument, student_id=str(student.pk), attempt=1
    )
    scale = CompetencyScale.objects.create(
        code="OBE-COMPETENCY",
        status="active",
        bands=[
            {"code": "BELUM", "min": 0, "max": 59.99},
            {"code": "CUKUP", "min": 60, "max": 74.99},
            {"code": "UNGGUL", "min": 75, "max": 100},
        ],
    )
    score = grade_submission(
        submission=submission,
        raw=Decimal("110"),
        maximum=Decimal("100"),
        assessor=assessor,
        rubric_trace={},
        scheme="CURRENT-AABBC",
        competency_scale=scale,
    )
    assert (score.normalized, score.letter, score.competency_category) == (
        Decimal("100"),
        "A",
        "UNGGUL",
    )
    second_submission = Submission.objects.create(
        instrument=instrument, student_id=str(student.pk), attempt=2
    )
    historical = record_historical_score(
        submission=second_submission,
        raw=Decimal("70"),
        maximum=Decimal("100"),
        normalized=Decimal("70"),
        letter="B",
        grade_point=Decimal("3"),
        assessor=assessor,
        scheme="LEGACY-ABCDE",
        scheme_version=1,
        source_version={"dataset": "v5"},
    )
    assert historical.letter == "B" and historical.rule_package == "LEGACY-ABCDE"
    assert best_attempt([historical, score]) == score
    assert requirement_met(historical)
    assert requirement_met(historical, thesis=True)
    historical.letter = "D"
    assert not requirement_met(historical)


@pytest.mark.django_db
def test_pr32_attendance_eligibility_uses_held_denominator_irs_and_override():
    lecturer, gpm, _, student = actors()
    offering, _ = offering_and_instrument(lecturer)
    roster = OfferingRoster.objects.create(
        offering=offering,
        student_id=str(student.pk),
        irs_status="approved",
        source_version={"irs": 1},
    )
    for index, status in enumerate(("present", "present", "permit", "absent", "cancelled"), 1):
        Attendance.objects.create(
            offering=offering,
            student_id=roster.student_id,
            activity_id=f"ACT-{index}",
            status=status,
            occurred_at=timezone.now() + timedelta(minutes=index),
            recorded_by=lecturer,
            source_version={"attendance": index},
        )
    snapshot = evaluate_exam_eligibility(roster=roster, generated_by=lecturer)
    assert snapshot.eligible and snapshot.attendance_percent == Decimal("75.00")
    assert snapshot.denominator == 4 and len(snapshot.counted_activity_ids) == 4
    roster.irs_status = "missing"
    roster.save(update_fields=["irs_status", "updated_at"])
    blocked = evaluate_exam_eligibility(roster=roster, generated_by=lecturer)
    assert not blocked.eligible and "IRS_NOT_APPROVED" in blocked.reason_codes
    override = request_exam_eligibility_override(
        roster=roster,
        user=lecturer,
        reason_code="IRS-SYNC-DELAY",
        reason="IRS sudah disahkan tetapi sinkronisasi terlambat",
        evidence_ids=["MANIFEST-1"],
    )
    with pytest.raises(ValidationError, match="Pemohon"):
        approve_exam_eligibility_override(override, user=lecturer)
    approve_exam_eligibility_override(override, user=gpm)
    overridden = evaluate_exam_eligibility(roster=roster, generated_by=gpm)
    assert overridden.eligible and overridden.override_id == override.pk


@pytest.mark.django_db
def test_pr33_submission_receipt_feedback_and_score_revision_maker_checker():
    assessor, checker, _, student = actors()
    deadline = timezone.now() + timedelta(hours=1)
    _, instrument = offering_and_instrument(assessor, code="ASSIGNMENT", deadline=deadline)
    group = SubmissionGroup.objects.create(
        instrument=instrument, code="G-01", member_ids=[str(student.pk)]
    )
    with pytest.raises(ValidationError, match="Anggota"):
        save_submission_draft(
            instrument=instrument,
            student_id="UNKNOWN",
            attempt=1,
            response={"answer": "x"},
            evidence_manifest_ids=[],
            group=group,
        )
    draft = save_submission_draft(
        instrument=instrument,
        student_id=str(student.pk),
        attempt=1,
        response={"answer": "versi-1"},
        evidence_manifest_ids=["MANIFEST-1"],
        group=group,
    )
    draft = save_submission_draft(
        instrument=instrument,
        student_id=str(student.pk),
        attempt=1,
        response={"answer": "versi-2"},
        evidence_manifest_ids=["MANIFEST-1"],
        group=group,
    )
    final = finalize_submission(draft, user=student)
    assert final.status == "final" and len(final.receipt_checksum) == 64
    final.response = {"tampered": True}
    with pytest.raises(ValidationError, match="immutable"):
        final.save()
    final.refresh_from_db()
    reopened = reopen_submission(final, user=assessor, reason="Perbaikan bukti")
    assert reopened.status == "reopened"
    late_time = deadline + timedelta(minutes=1)
    with pytest.raises(ValidationError, match="Deadline"):
        finalize_submission(reopened, user=student, now=late_time)
    final = finalize_submission(reopened, user=student, now=late_time, allow_late=True)
    assert final.late
    score = grade_submission(
        submission=final,
        raw=Decimal("70"),
        maximum=Decimal("100"),
        assessor=assessor,
        rubric_trace={},
        scheme="CURRENT-AABBC",
    )
    with pytest.raises(ValidationError, match="kriteria atau outcome"):
        set_score_feedback(score, user=assessor, feedback=[{"text": "Perbaiki"}])
    set_score_feedback(
        score,
        user=assessor,
        feedback=[{"outcome_code": "CPMK-01", "text": "Penalaran diperjelas"}],
    )
    revision = request_score_revision(
        score,
        user=assessor,
        raw=Decimal("80"),
        maximum=Decimal("100"),
        reason="Kesalahan penjumlahan",
    )
    with pytest.raises(ValidationError, match="Pemohon"):
        approve_score_revision(revision, user=assessor)
    replacement = approve_score_revision(revision, user=checker)
    assert replacement.state == "regraded" and replacement.normalized == Decimal("80.00")
    revision.refresh_from_db()
    assert revision.status == "approved" and revision.recalculation["letter"] == "AB"


@pytest.mark.django_db
def test_pr33_revises_rejected_evidence_as_a_new_record():
    first_manifest = FileManifest.objects.create(
        sha256="a" * 64,
        size=1,
        mime_type="application/pdf",
        owner_id="student-1",
        academic_object="submission:SUB-1",
        version=1,
        content_path="aa/aa/" + "a" * 64,
    )
    original = EvidenceRecord.objects.create(
        manifest=first_manifest,
        object_type="submission",
        object_id="SUB-1",
        status=EvidenceRecord.Status.REJECTED,
        rejection_reason="Halaman tidak lengkap",
    )
    replacement_manifest = FileManifest.objects.create(
        sha256="b" * 64,
        size=1,
        mime_type="application/pdf",
        owner_id="student-1",
        academic_object="submission:SUB-1",
        version=2,
        content_path="bb/bb/" + "b" * 64,
    )
    replacement = revise(
        original,
        replacement_manifest=replacement_manifest,
        actor_id="student-1",
        reason="Mengunggah halaman yang lengkap",
    )
    assert replacement.status == EvidenceRecord.Status.DRAFT
    assert replacement.supersedes == original
    assert replacement.revision_path == [str(original.public_id)]


@pytest.mark.django_db
def test_stage3_imports_all_operational_rows_idempotently(settings, monkeypatch, tmp_path):
    monkeypatch.setenv("OBE_DEMO_PASSWORD", f"runtime-{uuid.uuid4().hex}")
    dataset = json.loads(
        (settings.BASE_DIR / "fixtures/sample-data-2020-2026-obe-spec-v5.compact.json").read_text()
    )
    course = dataset["courses"][0]
    offering_id = "OFF-STAGE3-01"
    rps_id = "RPS-STAGE3-01"
    outcome_id = "CO-STAGE3-01"
    sub_id = "SCO-STAGE3-01"
    indicator_id = "IND-STAGE3-01"
    dataset["courseOfferings"] = [
        {
            "id": offering_id,
            "uuid": str(uuid.uuid4()),
            "courseCode": course["code"],
            "curriculumVersionId": "CURR-S1IF-2024-V1",
            "academicYear": "2024/2025",
            "semester": "odd",
            "classCode": "A",
            "parallelGroupId": "PG-STAGE3",
            "capacity": 40,
        }
    ]
    dataset["learning"] = {
        "rpsVersions": [
            {
                "id": rps_id,
                "uuid": str(uuid.uuid4()),
                "courseCode": course["code"],
                "courseOfferingId": offering_id,
                "version": 1,
                "status": "published-demo",
                "assessmentWeightTotal": 100,
            }
        ],
        "courseOutcomes": [
            {
                "id": outcome_id,
                "uuid": str(uuid.uuid4()),
                "rpsVersionId": rps_id,
                "localCode": "CPMK-01",
                "programCpmkId": course["cpmkIds"][0],
                "description": "Menerapkan konsep",
                "bloomLevel": "apply",
                "weight": 100,
                "target": 75,
            }
        ],
        "subOutcomes": [
            {
                "id": sub_id,
                "uuid": str(uuid.uuid4()),
                "courseOutcomeId": outcome_id,
                "code": "CPMK-01.01",
                "description": "Menyelesaikan masalah",
                "bloomLevel": "apply",
                "weightWithinCourseOutcome": 100,
                "target": 75,
            }
        ],
        "indicators": [
            {
                "id": indicator_id,
                "uuid": str(uuid.uuid4()),
                "subOutcomeId": sub_id,
                "description": "Menghasilkan artefak",
                "target": 75,
                "observable": True,
            }
        ],
        "weeklyPlans": [
            {
                "rpsVersionId": rps_id,
                "week": week,
                "subOutcomeIds": [sub_id],
                "indicatorIds": [] if week in {8, 16} else [indicator_id],
                "topic": f"Minggu {week}",
                "methods": ["assessment"] if week in {8, 16} else ["discussion"],
                "activities": ["exam"] if week in {8, 16} else ["learning"],
                "contactMinutes": 100,
                "structuredMinutes": 0 if week in {8, 16} else 120,
                "independentMinutes": 0 if week in {8, 16} else 120,
            }
            for week in range(1, 17)
        ],
    }
    rubric_id = "RUBRIC-STAGE3-V1"
    dataset["assessment"] = {
        "rubricLibrary": [
            {
                "id": rubric_id,
                "uuid": str(uuid.uuid4()),
                "version": 1,
                "type": "numeric-marking-scheme",
                "criteria": [{"code": "TOTAL", "name": "Total", "weight": 100}],
                "levels": [],
            }
        ],
        "assessmentPlans": [
            {
                "id": "ASM-STAGE3-01",
                "uuid": str(uuid.uuid4()),
                "rpsVersionId": rps_id,
                "instrumentCode": "FINAL",
                "name": "UAS",
                "weight": 100,
                "attemptLimit": 1,
                "rubricId": rubric_id,
                "outcomeMappings": [{"subOutcomeId": sub_id, "allocationWeight": 100}],
                "evidenceRequired": True,
            }
        ],
    }
    source = tmp_path / "stage3.json"
    report = tmp_path / "stage3-report.json"
    source.write_text(json.dumps(dataset), encoding="utf-8")
    call_command("import_obe_sample", path=source, report=report)
    first = json.loads(report.read_text())
    call_command("import_obe_sample", path=source, report=report)
    second = json.loads(report.read_text())
    assert second == first
    assert first["imported"]["course_offerings"] == 1
    assert first["imported"]["rps_versions"] == 1
    assert first["imported"]["weekly_plans"] == 16
    assert first["imported"]["assessment_instruments"] == 1
    for key in (
        "course_offerings",
        "rps_versions",
        "course_outcomes",
        "sub_outcomes",
        "indicators",
        "weekly_plans",
        "assessment_plans",
        "rubrics",
    ):
        assert key not in first["skipped"]
