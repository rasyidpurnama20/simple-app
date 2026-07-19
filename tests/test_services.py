import io
import json
import uuid
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from obe.academic_lifecycle.models import AcademicResult, StudentProfile
from obe.academic_lifecycle.services import calculate_progress, validate_plan
from obe.ai.gateway import AIUnavailable, complete
from obe.assessment.models import AssessmentInstrument, Submission
from obe.assessment.services import grade_submission
from obe.curriculum.models import Course, CurriculumEdge, CurriculumVersion
from obe.curriculum.services import activate, allocation_report
from obe.evidence.services import store
from obe.learning.models import Attendance, CourseOffering, RPSVersion
from obe.learning.services import attendance_eligibility, publish_rps
from obe.shared.models import AuditEvent, OutboxEvent
from obe.shared.services import ActorContext, record_change


@pytest.mark.django_db
def test_academic_progress_and_plan():
    user = get_user_model().objects.create_user("student")
    student = StudentProfile.objects.create(
        user=user, student_number="24001", cohort=2024, curriculum_public_id=uuid.uuid4()
    )
    course = uuid.uuid4()
    AcademicResult.objects.create(
        student=student,
        course_public_id=course,
        academic_year="2024/25",
        semester=1,
        attempt=1,
        credits=3,
        letter="C",
        grade_point=2,
        passed=True,
    )
    AcademicResult.objects.create(
        student=student,
        course_public_id=course,
        academic_year="2025/26",
        semester=3,
        attempt=2,
        credits=3,
        letter="A",
        grade_point=4,
        passed=True,
    )
    progress = calculate_progress(student)
    assert progress == {
        "attempted_credits": 3,
        "earned_credits": 3,
        "gpa": Decimal("4.00"),
        "remaining_credits": 141,
        "repeats": 1,
    }
    assert (
        validate_plan(student=student, semester=3, requested_credits=24, last_gpa=3).outcome
        == "pass"
    )
    with pytest.raises(ValidationError):
        validate_plan(student=student, semester=3, requested_credits=25, last_gpa=3)


@pytest.mark.django_db
def test_assessment_grading():
    assessor = get_user_model().objects.create_user("assessor")
    instrument = AssessmentInstrument.objects.create(
        offering_public_id=uuid.uuid4(),
        code="UTS",
        title="UTS",
        kind="written",
        weight=30,
        schedule=timezone.now(),
        assessor_id=str(assessor.pk),
        mappings=["CPL01"],
    )
    submission = Submission.objects.create(instrument=instrument, student_id="24001")
    score = grade_submission(
        submission=submission,
        raw=Decimal("80"),
        maximum=Decimal("100"),
        assessor=assessor,
        rubric_trace={"criterion": "C1"},
        scheme="CURRENT-AABBC",
    )
    assert (score.normalized, score.letter, score.grade_point) == (
        Decimal("80.00"),
        "AB",
        Decimal("3.5"),
    )


@pytest.mark.django_db
def test_curriculum_activation_and_invalid_allocation():
    curriculum = CurriculumVersion.objects.create(program_code="IF", name="OBE", cohort_from=2024)
    Course.objects.create(
        curriculum=curriculum,
        code="W001",
        name="Wajib",
        credits=126,
        required=True,
        recommended_semester=1,
        term="odd",
    )
    Course.objects.create(
        curriculum=curriculum,
        code="P001",
        name="Pilihan",
        credits=18,
        required=False,
        recommended_semester=7,
        term="odd",
    )
    CurriculumEdge.objects.create(
        curriculum=curriculum,
        source_type="PL",
        source_id="PL01",
        target_type="CPL",
        target_id="CPL01",
        allocation_weight=100,
    )
    assert allocation_report(curriculum)["valid"]
    activated = activate(curriculum)
    assert activated.status == "active" and len(activated.checksum) == 64
    edge = CurriculumEdge.objects.get(curriculum=curriculum)
    edge.allocation_weight = 99
    edge.save(update_fields=["allocation_weight"])
    assert not allocation_report(curriculum)["valid"]
    with pytest.raises(ValidationError):
        activate(curriculum)


@pytest.mark.django_db
def test_attendance_and_rps_publish():
    User = get_user_model()
    author, reviewer, approver = (
        User.objects.create_user(name) for name in ("author", "reviewer", "approver")
    )
    offering = CourseOffering.objects.create(
        course_public_id=uuid.uuid4(),
        academic_year="2025/26",
        semester="odd",
        class_code="A",
        coordinator=author,
    )
    for index, status in enumerate(["present", "present", "present", "absent"]):
        Attendance.objects.create(
            offering=offering,
            student_id="24001",
            activity_id=str(index),
            status=status,
            occurred_at=timezone.now(),
            recorded_by=author,
        )
    result = attendance_eligibility(offering_id=offering.id, student_id="24001")
    assert result["eligible"] and result["percent"] == Decimal("75.00")
    rps = RPSVersion.objects.create(
        offering=offering,
        authored_by=author,
        reviewed_by=reviewer,
        approved_by=approver,
        total_assessment_weight=100,
        content={"outcomes": ["CPL01"]},
    )
    assert publish_rps(rps).approval_snapshot["version"] == 1


@pytest.mark.django_db
def test_evidence_is_content_addressed(settings, tmp_path):
    settings.EVIDENCE_ROOT = tmp_path
    uploaded = SimpleUploadedFile(
        "evidence.pdf", b"verified evidence", content_type="application/pdf"
    )
    record = store(
        uploaded=uploaded,
        owner_id="24001",
        academic_object="submission:1",
        classification="internal",
    )
    target = tmp_path / record.manifest.content_path
    assert target.read_bytes() == b"verified evidence"
    assert record.manifest.sha256 in record.manifest.content_path
    with pytest.raises(ValidationError):
        store(
            uploaded=SimpleUploadedFile("bad.exe", b"bad", content_type="application/octet-stream"),
            owner_id="24001",
            academic_object="submission:2",
            classification="internal",
        )


@pytest.mark.django_db
def test_audit_and_outbox_are_atomic():
    audit = record_change(
        actor=ActorContext("1", "Prodi", "global"),
        action="activate",
        object_type="curriculum",
        object_id="IF-1",
        summary="activated",
        after={"status": "active"},
        reason="approved",
        event_type="curriculum.activated",
    )
    assert AuditEvent.objects.filter(pk=audit.pk).exists()
    assert OutboxEvent.objects.filter(payload__audit_id=str(audit.pk)).exists()
    assert len(audit.integrity_hash) == 64


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def test_ai_gateway_policy_success_and_fallback(settings, monkeypatch):
    settings.OBE_AI_ENABLED = True
    settings.LITELLM_URL = "http://gateway.internal"
    settings.LITELLM_API_KEY = "test-key"
    payload = {
        "choices": [{"message": {"content": "draft"}}],
        "model": "local-small",
        "usage": {"total_tokens": 3},
    }
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *_args, **_kwargs: FakeResponse(json.dumps(payload).encode()),
    )
    result = complete(
        model_alias="local-small",
        messages=[{"role": "user", "content": "help"}],
        data_class="internal",
    )
    assert result.content == "draft" and result.usage["total_tokens"] == 3
    with pytest.raises(PermissionError):
        complete(model_alias="external-approved", messages=[], data_class="restricted-exam")
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda *_args, **_kwargs: (_ for _ in ()).throw(TimeoutError())
    )
    with pytest.raises(AIUnavailable):
        complete(model_alias="local-small", messages=[], data_class="internal")
