import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone

from obe.assessment.models import (
    AssessmentInstrument,
    AssessmentItem,
    PerformanceLevel,
    Rubric,
    RubricCriterion,
    Submission,
)
from obe.assessment.selectors import assessment_item_payload
from obe.assessment.services import (
    assessment_plan_report,
    assessment_plan_snapshot,
    clone_rubric,
    grade_submission,
    grade_with_rubric,
    moderate_score,
    publish_assessment_plan,
    publish_rubric,
    regrade_submission,
    rubric_report,
)
from obe.learning.models import (
    CourseOffering,
    CourseOutcome,
    PerformanceIndicator,
    RPSVersion,
    SubOutcome,
    WeeklyPlan,
)
from obe.learning.services import (
    approve_rps,
    bulk_map_course_outcomes,
    clone_rps,
    generate_outcome_code,
    planned_vs_actual,
    publish_rps,
    record_week_execution,
    reschedule_week,
    return_rps,
    review_rps,
    rollback_rps,
    rps_diff,
    submit_rps_for_review,
    validate_rps,
)


def users():
    User = get_user_model()
    return tuple(User.objects.create_user(name) for name in ("pengampu", "gpm", "prodi", "marker"))


def valid_rps(author) -> RPSVersion:
    offering = CourseOffering.objects.create(
        course_public_id=uuid.uuid4(),
        curriculum_version_public_id=uuid.uuid4(),
        academic_year="2025/2026",
        semester="odd",
        class_code="A",
        coordinator=author,
        starts_on=date(2025, 8, 1),
        ends_on=date(2025, 12, 31),
    )
    rps = RPSVersion.objects.create(
        offering=offering,
        authored_by=author,
        total_assessment_weight=100,
        content={"references": ["Referensi uji"], "learning_materials": ["Materi uji"]},
    )
    outcome = CourseOutcome.objects.create(
        rps=rps,
        code="CPMK-01",
        description="Menerapkan konsep sistem",
        bloom_level="apply",
        target=75,
        weight=100,
        program_cpmk_ids=["CPMK14"],
        cpl_ids=["CPL02"],
    )
    sub = SubOutcome.objects.create(
        rps=rps,
        course_outcome=outcome,
        code="CPMK-01.01",
        description="Menyelesaikan masalah terstruktur",
        bloom_level="apply",
        target=75,
        weight=100,
    )
    indicator = PerformanceIndicator.objects.create(
        rps=rps,
        sub_outcome=sub,
        code="IND-01",
        description="Menghasilkan artefak terukur",
        target=75,
        observable=True,
    )
    for week in range(1, 17):
        exam = week in {8, 16}
        WeeklyPlan.objects.create(
            rps=rps,
            week=week,
            meeting_type="midterm" if week == 8 else "final" if week == 16 else "regular",
            outcomes=[sub.code],
            indicators=[] if exam else [indicator.code],
            material="UTS" if week == 8 else "UAS" if week == 16 else f"Materi {week}",
            methods=["assessment"] if exam else ["problem-based-learning"],
            activities=["exam"] if exam else ["guided-practice"],
            contact_minutes=90 if exam else 150,
            structured_minutes=0 if exam else 180,
            independent_minutes=0 if exam else 180,
            planned_date=offering.starts_on + timedelta(days=(week - 1) * 7),
        )
    rps.content = {
        **rps.content,
        "assessment_snapshot": [
            {
                "code": "ASSESSMENT",
                "weight": "100",
                "status": "published",
                "published_before_teaching": True,
                "mappings": [{"indicator_codes": [indicator.code]}],
            }
        ],
    }
    rps.save(update_fields=["content", "updated_at"])
    return rps


def draft_rubric() -> Rubric:
    rubric = Rubric.objects.create(code="RUB-UJI", title="Rubrik Uji", kind="analytic")
    for order, code, weight in ((1, "ACCURACY", 60), (2, "METHOD", 40)):
        RubricCriterion.objects.create(
            rubric=rubric,
            code=code,
            title=code.title(),
            description=f"Kriteria {code}",
            weight=weight,
            indicator_codes=["IND-01"],
            sub_outcome_codes=["CPMK-01.01"],
            order=order,
        )
    PerformanceLevel.objects.create(
        rubric=rubric,
        code="L1",
        descriptor="Perlu perbaikan",
        minimum=0,
        maximum=59.99,
        points=50,
        order=1,
    )
    PerformanceLevel.objects.create(
        rubric=rubric,
        code="L2",
        descriptor="Kompeten",
        minimum=60,
        maximum=100,
        points=80,
        order=2,
    )
    return rubric


@pytest.mark.django_db
def test_rps_lifecycle_snapshot_immutability_clone_and_diff():
    author, reviewer, approver, _ = users()
    rps = valid_rps(author)
    assert validate_rps(rps)["valid"]

    rps = submit_rps_for_review(rps, user=author, expected_lock_version=0)
    rps = review_rps(rps, user=reviewer, expected_lock_version=1)
    rps = approve_rps(rps, user=approver, expected_lock_version=2)
    rps = publish_rps(rps, user=approver, strict=True)
    assert rps.status == "published"
    assert rps.approval_snapshot["checksum"] == rps.content_checksum
    assert rps.approval_snapshot["payload"]["indicators"][0]["code"] == "IND-01"

    outcome = rps.course_outcomes.get()
    outcome.description = "Mutasi outcome"
    with pytest.raises(ValidationError, match="immutable"):
        outcome.save()
    week = rps.weekly_plans.get(week=1)
    week.material = "Mutasi materi"
    with pytest.raises(ValidationError, match="immutable"):
        week.save()

    rps.content = {"mutated": True}
    with pytest.raises(ValidationError, match="immutable"):
        rps.save()

    clone = clone_rps(rps, user=author, revision_reason="Pembaruan materi")
    clone.content = {**clone.content, "learning_materials": ["Materi revisi"]}
    clone.save(update_fields=["content", "updated_at"])
    assert clone.version == 2 and clone.status == "draft"
    assert rps_diff(rps, clone)["changed"]["content"]
    clone = submit_rps_for_review(clone, user=author)
    clone = review_rps(clone, user=reviewer)
    clone = approve_rps(clone, user=approver)
    clone = publish_rps(clone, user=approver, strict=True)
    rollback = rollback_rps(clone, rps, user=author, reason="Versi dua tidak sesuai")
    assert rollback.version == 3 and "Rollback" in rollback.revision_reason


@pytest.mark.django_db
def test_rps_return_comments_stale_approval_and_concurrent_review():
    author, reviewer, approver, _ = users()
    rps = submit_rps_for_review(valid_rps(author), user=author)
    with pytest.raises(ValidationError, match="Optimistic lock"):
        review_rps(rps, user=reviewer, expected_lock_version=0)
    returned = return_rps(
        rps,
        user=reviewer,
        field_path="weekly_plans.4.material",
        comment="Materi perlu dibuat lebih terukur",
        expected_lock_version=1,
    )
    assert returned.field_comments.get().field_path == "weekly_plans.4.material"

    returned = submit_rps_for_review(returned, user=author)
    reviewed = review_rps(returned, user=reviewer)
    RPSVersion.objects.filter(pk=reviewed.pk).update(content={**reviewed.content, "changed": True})
    with pytest.raises(ValidationError, match="stale"):
        approve_rps(reviewed, user=approver)


@pytest.mark.django_db
@pytest.mark.parametrize("weight", [Decimal("99"), Decimal("101")])
def test_rps_validation_blocks_invalid_assessment_weight(weight):
    author, _, _, _ = users()
    rps = valid_rps(author)
    rps.content["assessment_snapshot"][0]["weight"] = str(weight)
    rps.total_assessment_weight = weight
    rps.save(update_fields=["content", "total_assessment_weight", "updated_at"])
    report = validate_rps(rps)
    assert not report["valid"]
    assert "ASSESSMENT_WEIGHT_NOT_100" in {row["code"] for row in report["errors"]}


@pytest.mark.django_db
def test_rps_design_validation_mapping_and_week_execution_edges():
    author, reviewer, _, _ = users()
    offering = CourseOffering(
        course_public_id=uuid.uuid4(),
        academic_year="2025/2026",
        semester="short",
        class_code="SP",
        coordinator=author,
        delivery_mode="short",
        starts_on=date(2025, 7, 1),
        ends_on=date(2025, 6, 1),
    )
    with pytest.raises(ValidationError):
        offering.full_clean()
    offering.ends_on = date(2025, 7, 31)
    with pytest.raises(ValidationError, match="konfigurasi kalender"):
        offering.full_clean()

    empty_offering = CourseOffering.objects.create(
        course_public_id=uuid.uuid4(),
        academic_year="2025/2026",
        semester="odd",
        class_code="B",
        coordinator=author,
    )
    empty = RPSVersion.objects.create(offering=empty_offering, authored_by=author, content={})
    codes = {row["code"] for row in validate_rps(empty)["errors"]}
    assert {"RPS_REQUIRED_FIELD_MISSING", "COURSE_OUTCOME_MISSING", "WEEKLY_PLAN_NOT_16"} <= codes
    with pytest.raises(ValidationError):
        publish_rps(empty, user=author, strict=True)
    with pytest.raises(ValidationError, match="published dan alasan"):
        clone_rps(empty, user=author, revision_reason="")

    rps = valid_rps(author)
    assert generate_outcome_code(rps) == "CPMK-02"
    with pytest.raises(ValidationError, match="tidak dikenal"):
        bulk_map_course_outcomes(
            rps,
            mappings={"CPMK-99": {"program_cpmk_ids": ["CPMK99"], "cpl_ids": ["CPL99"]}},
            user=author,
        )
    with pytest.raises(ValidationError, match="wajib memiliki"):
        bulk_map_course_outcomes(
            rps,
            mappings={"CPMK-01": {"program_cpmk_ids": [], "cpl_ids": ["CPL02"]}},
            user=author,
        )
    bulk_map_course_outcomes(
        rps,
        mappings={"CPMK-01": {"program_cpmk_ids": ["CPMK14"], "cpl_ids": ["CPL02"]}},
        user=author,
    )
    rps.refresh_from_db()
    assert rps.content["mapping_history"][0]["code"] == "CPMK-01"

    plan = rps.weekly_plans.get(week=1)
    with pytest.raises(ValidationError, match="published plan"):
        reschedule_week(
            plan, user=author, new_date=plan.planned_date + timedelta(days=1), reason=""
        )
    rps = submit_rps_for_review(rps, user=author)
    rps = review_rps(rps, user=reviewer)
    with pytest.raises(ValidationError, match="Komentar pengembalian"):
        return_rps(rps, user=reviewer, comment="")
    rps.status = RPSVersion.Status.PUBLISHED
    RPSVersion.objects.filter(pk=rps.pk).update(status=RPSVersion.Status.PUBLISHED)
    plan.refresh_from_db()
    with pytest.raises(ValidationError, match="di luar semester"):
        reschedule_week(plan, user=author, new_date=date(2026, 1, 1), reason="Pindah")
    reschedule_week(
        plan, user=author, new_date=plan.planned_date + timedelta(days=1), reason="Hari libur"
    )
    with pytest.raises(ValidationError, match="belum lengkap"):
        record_week_execution(plan, user=author, actual={})
    actual = {
        "occurred_at": timezone.now().isoformat(),
        "minutes": 0,
        "attendance_count": 30,
        "materials": ["Materi 1"],
        "evidence_ids": ["E-1"],
    }
    with pytest.raises(ValidationError, match="lebih dari nol"):
        record_week_execution(plan, user=author, actual=actual)
    actual["minutes"] = 145
    actual["deviation_reason"] = "Diskusi lebih singkat"
    record_week_execution(plan, user=author, actual=actual)
    report = planned_vs_actual(rps)
    assert report[0]["deviation_minutes"] == 145 - 510
    assert report[1]["actual_minutes"] is None


@pytest.mark.django_db
def test_validation_reports_all_broken_design_dimensions():
    author, _, _, _ = users()
    rps = valid_rps(author)
    outcome = rps.course_outcomes.get()
    sub = rps.sub_outcomes.get()
    indicator = rps.indicators.get()
    CourseOutcome.objects.filter(pk=outcome.pk).update(weight=99, program_cpmk_ids=[], cpl_ids=[])
    SubOutcome.objects.filter(pk=sub.pk).update(weight=99)
    PerformanceIndicator.objects.filter(pk=indicator.pk).update(observable=False, description="")
    WeeklyPlan.objects.filter(rps=rps, week=8).update(meeting_type="regular", methods=[])
    WeeklyPlan.objects.filter(rps=rps, week=16).update(meeting_type="regular", methods=["unknown"])
    WeeklyPlan.objects.filter(rps=rps, week=1).update(
        contact_minutes=0, planned_date=date(2026, 1, 1)
    )
    rps.content = {"references": [], "learning_materials": [], "assessment_snapshot": []}
    rps.save(update_fields=["content", "updated_at"])
    codes = {row["code"] for row in validate_rps(rps)["errors"]}
    assert {
        "COURSE_OUTCOME_WEIGHT_NOT_100",
        "COURSE_OUTCOME_MAPPING_BROKEN",
        "SUB_OUTCOME_WEIGHT_NOT_100",
        "INDICATOR_NOT_OBSERVABLE",
        "MIDTERM_WEEK_MISSING",
        "FINAL_WEEK_MISSING",
        "LEARNING_METHOD_INVALID",
        "LEARNING_TIME_INVALID",
        "WEEK_DATE_OUTSIDE_SEMESTER",
        "ASSESSMENT_PLAN_MISSING",
        "ASSESSMENT_MAPPING_INCOMPLETE",
    } <= codes


@pytest.mark.django_db
def test_assessment_blueprint_rubric_trace_answer_key_moderation_and_regrade():
    author, _, _, second_marker = users()
    rubric = publish_rubric(draft_rubric(), user=author)
    offering_id, rps_id = uuid.uuid4(), uuid.uuid4()
    instruments = []
    for code, weight in (("TUGAS", 40), ("UAS", 60)):
        instruments.append(
            AssessmentInstrument.objects.create(
                offering_public_id=offering_id,
                rps_public_id=rps_id,
                code=code,
                title=code,
                kind="summative",
                purpose=f"Mengukur {code}",
                participant_scope={"class": "A"},
                weight=weight,
                schedule=timezone.now() + timedelta(days=7),
                assessor_id=str(author.pk),
                mappings=[
                    {
                        "sub_outcome_codes": ["CPMK-01.01"],
                        "indicator_codes": ["IND-01"],
                        "allocation_weight": 100,
                    }
                ],
                blueprint={
                    "outcome_distribution": {"IND-01": 100},
                    "difficulty": "mixed",
                    "form": "constructed-response",
                    "durationMinutes": 90,
                    "coverage": ["IND-01"],
                },
                rubric_public_id=rubric.public_id,
            )
        )
    item = AssessmentItem.objects.create(
        instrument=instruments[0],
        code="ITEM-01",
        prompt="Jelaskan solusi",
        item_type="constructed-response",
        points=100,
        indicator_codes=["IND-01"],
        sub_outcome_codes=["CPMK-01.01"],
        answer_key={"secret": "jawaban"},
    )
    teaching_starts = timezone.now() + timedelta(days=1)
    published = publish_assessment_plan(
        instruments, user=author, teaching_starts_at=teaching_starts
    )
    assert sum(Decimal(item["weight"]) for item in assessment_plan_snapshot(published)) == 100
    assert "answer_key" not in assessment_item_payload(item)
    assert assessment_item_payload(item, can_view_answer_key=True)["answer_key"]
    item.prompt = "Mutasi terlarang"
    with pytest.raises(ValidationError, match="immutable"):
        item.save()
    criterion = rubric.criteria.first()
    criterion.weight = 50
    with pytest.raises(ValidationError, match="immutable"):
        criterion.save()

    submission = Submission.objects.create(instrument=published[0], student_id="24001")
    score = grade_with_rubric(
        submission=submission,
        rubric=rubric,
        criterion_points={"ACCURACY": Decimal("80"), "METHOD": Decimal("70")},
        assessor=author,
        scheme="CURRENT-AABBC",
        second_assessor=second_marker,
        blind_reference="BLIND-001",
    )
    assert score.normalized == Decimal("76.00")
    assert score.criterion_scores.count() == 2
    assert score.rubric_trace["response_version"] == submission.version
    moderate_score(score, user=second_marker, comment="Hasil kedua marker konsisten")
    score.refresh_from_db()
    assert score.moderation_state == "reconciled"

    rubric.title = "Mutasi"
    with pytest.raises(ValidationError, match="immutable"):
        rubric.save()
    revised = clone_rubric(rubric, user=author)
    publish_rubric(revised, user=author)
    replacement = regrade_submission(
        previous=score,
        new_rubric=revised,
        criterion_points={"ACCURACY": Decimal("90"), "METHOD": Decimal("80")},
        assessor=author,
        scheme="CURRENT-AABBC",
        reason="Moderasi program studi",
    )
    assert replacement.normalized == Decimal("86.00")
    assert replacement.rubric_trace["supersedes_score"] == str(score.public_id)
    assert rubric_report(revised)["valid"]


@pytest.mark.django_db
def test_assessment_validation_and_grading_error_paths():
    author, _, _, second_marker = users()
    invalid_rubric = Rubric.objects.create(code="BAD", title="Bad", kind="analytic")
    report = rubric_report(invalid_rubric)
    assert {row["code"] for row in report["errors"]} == {
        "RUBRIC_CRITERION_MISSING",
        "RUBRIC_WEIGHT_NOT_100",
        "RUBRIC_LEVEL_MISSING",
    }
    with pytest.raises(ValidationError):
        publish_rubric(invalid_rubric, user=author)
    criterion = RubricCriterion.objects.create(
        rubric=invalid_rubric,
        code="C1",
        title="C1",
        description="",
        weight=99,
        indicator_codes=[],
        sub_outcome_codes=[],
    )
    with pytest.raises(ValidationError):
        criterion.full_clean()
    PerformanceLevel.objects.create(
        rubric=invalid_rubric,
        code="L1",
        descriptor="Rendah",
        minimum=0,
        maximum=60,
        points=50,
    )
    PerformanceLevel.objects.create(
        rubric=invalid_rubric,
        code="L2",
        descriptor="Tumpang tindih",
        minimum=60,
        maximum=100,
        points=80,
    )
    codes = {row["code"] for row in rubric_report(invalid_rubric)["errors"]}
    assert {"RUBRIC_MAPPING_MISSING", "RUBRIC_LEVEL_OVERLAP"} <= codes

    offering_id = uuid.uuid4()
    first = AssessmentInstrument.objects.create(
        offering_public_id=offering_id,
        code="BAD",
        title="Bad",
        kind="quiz",
        weight=99,
        schedule=timezone.now() - timedelta(days=1),
        assessor_id=str(author.pk),
        mappings=[{"allocation_weight": 99}],
        blueprint={},
        evidence_required=False,
    )
    second = AssessmentInstrument.objects.create(
        offering_public_id=offering_id,
        code="BAD",
        version=2,
        title="Bad 2",
        kind="quiz",
        weight=1,
        schedule=timezone.now() - timedelta(days=1),
        assessor_id=str(author.pk),
        mappings=[],
        blueprint={},
    )
    plan_codes = {
        row["code"]
        for row in assessment_plan_report([first, second], teaching_starts_at=timezone.now())[
            "errors"
        ]
    }
    assert {
        "ASSESSMENT_CODE_DUPLICATE",
        "ASSESSMENT_MAPPING_MISSING",
        "ASSESSMENT_BLUEPRINT_MISSING",
        "ASSESSMENT_EVIDENCE_NOT_REQUIRED",
        "ASSESSMENT_MAPPING_WEIGHT_NOT_100",
        "ASSESSMENT_MAPPING_BROKEN",
        "ASSESSMENT_SCHEDULE_BEFORE_TEACHING",
    } <= plan_codes
    with pytest.raises(ValidationError):
        publish_assessment_plan([first, second], user=author, teaching_starts_at=timezone.now())

    rubric = publish_rubric(draft_rubric(), user=author)
    instrument = AssessmentInstrument.objects.create(
        offering_public_id=uuid.uuid4(),
        code="QUIZ",
        title="Quiz",
        kind="quiz",
        purpose="Mengukur capaian",
        weight=100,
        schedule=timezone.now(),
        assessor_id=str(author.pk),
        mappings=[
            {
                "allocation_weight": 100,
                "indicator_codes": ["IND-01"],
                "sub_outcome_codes": ["CPMK-01.01"],
            }
        ],
        blueprint={
            "outcome_distribution": {},
            "difficulty": "mixed",
            "form": "quiz",
            "durationMinutes": 30,
            "coverage": ["IND-01"],
        },
        status="published",
    )
    submission = Submission.objects.create(instrument=instrument, student_id="24002")
    with pytest.raises(ValidationError, match="Snapshot publikasi"):
        grade_submission(
            submission=submission,
            raw=Decimal("70"),
            maximum=100,
            assessor=author,
            rubric_trace={},
            scheme="CURRENT-AABBC",
        )
    instrument.status = "draft"
    with pytest.raises(ValidationError, match="Rubrik harus"):
        grade_with_rubric(
            submission=submission,
            rubric=invalid_rubric,
            criterion_points={"C1": Decimal("70")},
            assessor=author,
            scheme="CURRENT-AABBC",
        )
    with pytest.raises(ValidationError, match="tepat satu"):
        grade_with_rubric(
            submission=submission,
            rubric=rubric,
            criterion_points={},
            assessor=author,
            scheme="CURRENT-AABBC",
        )
    with pytest.raises(ValidationError, match="0–100"):
        grade_with_rubric(
            submission=submission,
            rubric=rubric,
            criterion_points={"ACCURACY": Decimal("101"), "METHOD": Decimal("70")},
            assessor=author,
            scheme="CURRENT-AABBC",
        )
    valid_score = grade_with_rubric(
        submission=submission,
        rubric=rubric,
        criterion_points={"ACCURACY": Decimal("70"), "METHOD": Decimal("70")},
        assessor=author,
        scheme="CURRENT-AABBC",
    )
    with pytest.raises(ValidationError, match="second marker"):
        moderate_score(valid_score, user=second_marker, comment="Tidak berwenang")
    with pytest.raises(ValidationError, match="alasan"):
        regrade_submission(
            previous=valid_score,
            new_rubric=rubric,
            criterion_points={"ACCURACY": Decimal("70"), "METHOD": Decimal("70")},
            assessor=author,
            scheme="CURRENT-AABBC",
            reason="",
        )
    with pytest.raises(ValidationError, match="versi rubrik baru"):
        regrade_submission(
            previous=valid_score,
            new_rubric=rubric,
            criterion_points={"ACCURACY": Decimal("70"), "METHOD": Decimal("70")},
            assessor=author,
            scheme="CURRENT-AABBC",
            reason="Coba ulang",
        )
