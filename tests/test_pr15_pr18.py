from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.utils import timezone

from obe.quality.integrity import (
    assert_data_usable,
    persist_validation,
    transition_issue,
    validate_collection,
    validate_record,
)
from obe.quality.models import IntegrityIssue, IntegrityValidationRun
from obe.shared.academic_rules import (
    activate_rule,
    decide_override,
    effective_outcome,
    evaluate_and_record,
    evaluate_rule,
    replay_decision,
    request_override,
    resolve_rule_package,
    review_rule,
    select_active_rule,
    submit_appeal,
    transition_appeal,
)
from obe.shared.models import (
    AcademicAppeal,
    AcademicRule,
    CohortRulePackage,
    DecisionOverride,
)
from obe.shared.rules import (
    grade_for,
    graduation_eligibility,
    max_credit_load,
    package_for_cohort,
    progress_evaluation,
)
from obe.shared.services import ActorContext


@pytest.fixture
def actors(django_user_model):
    maker = django_user_model.objects.create_user("maker")
    reviewer = django_user_model.objects.create_user("reviewer")
    checker = django_user_model.objects.create_user("checker")
    student = django_user_model.objects.create_user("student")
    return maker, reviewer, checker, student


def actor(user) -> ActorContext:
    return ActorContext(str(user.pk), user.username, "test")


def active_rule(maker, checker, *, code="SCORE-MIN-60", version=1, priority=100):
    return AcademicRule.objects.create(
        code=code,
        version=version,
        scope={"type": "course-result"},
        input_schema={"required": ["score"]},
        expression={"score": {"gte": 60}},
        priority=priority,
        severity="blocking",
        effective_from=date(2024, 1, 1),
        status=AcademicRule.Status.ACTIVE,
        created_by=maker,
        reviewed_by=checker,
        activated_by=checker,
        activated_at=timezone.now(),
    )


def active_package(maker, checker, *, code="CURRENT-AABBC", cohort_from=2024, version=1):
    return CohortRulePackage.objects.create(
        code=code,
        version=version,
        status=CohortRulePackage.Status.ACTIVE,
        cohort_from=cohort_from,
        effective_from=date(2024, 1, 1),
        grade_scheme=[{"grade": "A", "min": 85, "max": 100, "gradePoint": 4}],
        minimum_passing_grade="C",
        minimum_thesis_grade="B",
        created_by=maker,
        activated_by=checker,
        activated_at=timezone.now(),
    )


@pytest.mark.django_db
def test_pr15_evaluation_is_deterministic_and_explained(actors):
    maker, _, checker, _ = actors
    rule = active_rule(maker, checker)
    first = evaluate_rule(
        rule,
        {"score": Decimal("60.00")},
        object_type="course-result",
        object_id="RESULT-1",
        source_versions={"score": "gradebook@7"},
    )
    second = evaluate_rule(
        rule,
        {"score": Decimal("60.00")},
        object_type="course-result",
        object_id="RESULT-1",
        source_versions={"score": "gradebook@7"},
    )
    assert first == second
    assert first.outcome == "pass"
    assert first.reason_code == "SCORE-MIN-60_PASS"
    assert first.evidence_rows[0]["source_version"] == "gradebook@7"
    assert "versi 1" in first.explanation


@pytest.mark.django_db
def test_pr15_missing_input_boundary_and_invalid_operator(actors):
    maker, _, checker, _ = actors
    rule = active_rule(maker, checker)
    missing = evaluate_rule(rule, {}, object_type="course-result", object_id="R-1")
    failed = evaluate_rule(rule, {"score": 59.99}, object_type="course-result", object_id="R-1")
    assert missing.outcome == "indeterminate"
    assert failed.outcome == "fail"
    rule.status = AcademicRule.Status.RETIRED
    rule.save(update_fields=["status", "updated_at"])
    with pytest.raises(ValidationError, match="Hanya rule aktif"):
        evaluate_rule(rule, {"score": 60}, object_type="course-result", object_id="R-1")


@pytest.mark.django_db
def test_pr15_decision_snapshot_is_idempotent_immutable_and_replayable(actors):
    maker, _, checker, _ = actors
    rule = active_rule(maker, checker)
    first = evaluate_and_record(
        rule,
        {"score": 75},
        object_type="course-result",
        object_id="RESULT-2",
        actor=actor(checker),
        source_versions={"score": "gradebook@8"},
    )
    second = evaluate_and_record(
        rule,
        {"score": 75},
        object_type="course-result",
        object_id="RESULT-2",
        actor=actor(checker),
        source_versions={"score": "gradebook@8"},
    )
    assert first.pk == second.pk
    assert replay_decision(first).decision_hash == first.decision_hash
    first.reason_code = "TAMPERED"
    with pytest.raises(ValidationError, match="immutable"):
        first.save()
    with pytest.raises(ValidationError, match="tidak boleh dihapus"):
        first.delete()


@pytest.mark.django_db
def test_pr15_rule_workflow_enforces_maker_checker_and_retires_previous(actors):
    maker, reviewer, checker, _ = actors
    previous = active_rule(maker, checker, version=1)
    draft = AcademicRule.objects.create(
        code=previous.code,
        version=2,
        scope={"type": "course-result"},
        input_schema={"required": ["score"]},
        expression={"score": {"gte": 65}},
        priority=90,
        severity="blocking",
        effective_from=date(2025, 1, 1),
        status=AcademicRule.Status.DRAFT,
        created_by=maker,
    )
    with pytest.raises(ValidationError, match="mereview sendiri"):
        review_rule(draft, reviewer=maker, actor=actor(maker), note="self review")
    reviewed = review_rule(draft, reviewer=reviewer, actor=actor(reviewer), note="reviewed")
    with pytest.raises(ValidationError, match="Maker dan checker"):
        activate_rule(reviewed, checker=maker, actor=actor(maker), reason="self activation")
    activated = activate_rule(
        reviewed,
        checker=checker,
        actor=actor(checker),
        reason="approved replacement",
    )
    previous.refresh_from_db()
    assert activated.status == AcademicRule.Status.ACTIVE
    assert previous.status == AcademicRule.Status.RETIRED
    activated.expression = {"score": {"gte": 0}}
    with pytest.raises(ValidationError, match="immutable"):
        activated.save()


@pytest.mark.django_db
def test_pr15_priority_conflict_is_fail_closed(actors):
    maker, _, checker, _ = actors
    active_rule(maker, checker, code="CONFLICT", version=1, priority=10)
    active_rule(maker, checker, code="CONFLICT", version=2, priority=10)
    with pytest.raises(ValidationError, match="Priority conflict"):
        select_active_rule(
            code="CONFLICT",
            scope="course-result",
            cohort=2024,
            on_date=date(2024, 6, 1),
        )


@pytest.mark.parametrize(
    ("cohort", "package"),
    [(2020, "LEGACY-ABCDE"), (2023, "LEGACY-ABCDE"), (2024, "CURRENT-AABBC")],
)
def test_pr16_cohort_resolves_exactly_one_static_package(cohort, package):
    assert package_for_cohort(cohort) == package


def test_pr16_grade_credit_progress_and_graduation_boundaries():
    assert grade_for(50.99, "LEGACY-ABCDE") == ("E", Decimal("0"))
    assert grade_for(51, "LEGACY-ABCDE") == ("D", Decimal("1"))
    assert grade_for(84.99, "CURRENT-AABBC") == ("AB", Decimal("3.5"))
    assert max_credit_load(semester=2, last_gpa=1.99, returning=False).reason_code.endswith("18")
    assert max_credit_load(semester=3, last_gpa=2.5, returning=False).reason_code.endswith("22")
    assert max_credit_load(semester=8, last_gpa=4, returning=True).reason_code == "RETURNING_MAX_18"
    assert (
        progress_evaluation(
            package="CURRENT-AABBC",
            semester=3,
            timing="start",
            earned_credits=25,
            gpa=2.5,
        ).outcome
        == "pass"
    )
    assert (
        progress_evaluation(
            package="CURRENT-AABBC",
            semester=5,
            timing="start",
            earned_credits=49,
            gpa=3,
        ).outcome
        == "fail"
    )
    assert (
        progress_evaluation(
            package="CURRENT-AABBC",
            semester=13,
            timing="start",
            earned_credits=108,
            gpa=None,
        ).outcome
        == "indeterminate"
    )
    valid = {
        "total_credits": 144,
        "required_credits": 126,
        "elective_credits": 18,
        "pkl": True,
        "kkn": True,
        "thesis_credits": 6,
        "thesis_grade": "B",
        "english_score": 400,
        "status": "active",
        "repository_complete": True,
    }
    decision = graduation_eligibility(valid)
    assert decision.outcome == "pass"
    assert decision.trace[0] == "package=CURRENT-AABBC"


@pytest.mark.django_db
def test_pr16_database_package_resolution_rejects_zero_or_multiple(actors):
    maker, _, checker, _ = actors
    with pytest.raises(ValidationError, match="ditemukan 0"):
        resolve_rule_package(cohort=2024, on_date=date(2024, 6, 1))
    first = active_package(maker, checker)
    assert resolve_rule_package(cohort=2024, on_date=date(2024, 6, 1)) == first
    active_package(maker, checker, code="CURRENT-OTHER", version=1)
    with pytest.raises(ValidationError, match="ditemukan 2"):
        resolve_rule_package(cohort=2024, on_date=date(2024, 6, 1))


@pytest.mark.django_db
def test_pr16_sample_v5_import_seeds_rules_and_packages_idempotently(settings, monkeypatch):
    settings.OBE_ENV = "test"
    settings.DEBUG = True
    monkeypatch.setenv("OBE_DEMO_PASSWORD", "test-only-password-123")
    call_command("import_obe_sample", student_limit=0, verbosity=0)
    call_command("import_obe_sample", student_limit=0, verbosity=0)
    assert CohortRulePackage.objects.count() == 2
    assert AcademicRule.objects.count() == 11
    assert AcademicRule.objects.filter(status=AcademicRule.Status.ACTIVE).count() == 11


@pytest.mark.django_db
def test_pr17_override_requires_authority_evidence_and_independent_checker(actors):
    maker, _, checker, _ = actors
    rule = active_rule(maker, checker)
    decision = evaluate_and_record(
        rule,
        {"score": 50},
        object_type="course-result",
        object_id="RESULT-FAIL",
        actor=actor(checker),
    )
    with pytest.raises(PermissionDenied):
        request_override(
            decision,
            maker=maker,
            actor=actor(maker),
            authorized=False,
            reason_code="EXCEPTION",
            reason="documented exception",
            evidence_documents=[{"manifest": "FILE-1"}],
            impact="UAS permitted once",
        )
    override = request_override(
        decision,
        maker=maker,
        actor=actor(maker),
        authorized=True,
        reason_code="EXCEPTION",
        reason="documented exception",
        evidence_documents=[{"manifest": "FILE-1"}],
        impact="UAS permitted once",
        valid_to=timezone.now() + timedelta(days=7),
    )
    with pytest.raises(ValidationError, match="Maker"):
        decide_override(
            override,
            checker=maker,
            actor=actor(maker),
            authorized=True,
            approve=True,
            note="self",
        )
    approved = decide_override(
        override,
        checker=checker,
        actor=actor(checker),
        authorized=True,
        approve=True,
        note="evidence verified",
    )
    assert approved.status == DecisionOverride.Status.APPROVED
    assert effective_outcome(decision) == "overridden"
    assert decision.input_snapshot == {"score": 50}


@pytest.mark.django_db
def test_pr17_appeal_follows_explicit_state_machine(actors):
    maker, reviewer, checker, student = actors
    rule = active_rule(maker, checker)
    decision = evaluate_and_record(
        rule,
        {"score": 50},
        object_type="course-result",
        object_id="RESULT-APPEAL",
        actor=actor(checker),
    )
    appeal = submit_appeal(
        decision,
        submitted_by=student,
        statement="Nilai sumber belum memuat remedial.",
        evidence_documents=[{"manifest": "FILE-2"}],
        expires_at=timezone.now() + timedelta(days=14),
        actor=actor(student),
    )
    with pytest.raises(ValidationError, match="pemohon|Pemohon"):
        transition_appeal(
            appeal,
            reviewer=student,
            actor=actor(student),
            target=AcademicAppeal.Status.REVIEWED,
            note="self review",
        )
    appeal = transition_appeal(
        appeal,
        reviewer=reviewer,
        actor=actor(reviewer),
        target=AcademicAppeal.Status.INFORMATION_NEEDED,
        note="Lampirkan berita acara remedial.",
    )
    appeal = transition_appeal(
        appeal,
        reviewer=reviewer,
        actor=actor(reviewer),
        target=AcademicAppeal.Status.REVIEWED,
        note="Bukti diterima.",
    )
    appeal = transition_appeal(
        appeal,
        reviewer=reviewer,
        actor=actor(reviewer),
        target=AcademicAppeal.Status.APPROVED,
        note="Banding diterima.",
    )
    appeal = transition_appeal(
        appeal,
        reviewer=reviewer,
        actor=actor(reviewer),
        target=AcademicAppeal.Status.CLOSED,
        note="Selesai.",
    )
    assert appeal.closed_at is not None


def test_pr18_validator_finds_blocking_warning_duplicate_and_orphan():
    records = [
        {
            "id": "A",
            "code": "COURSE-1",
            "credits": 0,
            "semester": 15,
            "score": 101,
            "weights": [{"weight": 60}, {"weight": 39}],
            "effective_from": "2025-02-01",
            "effective_to": "2025-01-01",
            "checksum": "bad",
            "evidence_required": True,
        },
        {"id": "B", "code": "COURSE-1", "credits": 3, "parent_id": "MISSING"},
    ]
    issues = validate_collection(records, object_type="course")
    codes = {issue.reason_code for issue in issues}
    assert {
        "CREDITS_OUT_OF_RANGE",
        "SEMESTER_OUT_OF_RANGE",
        "VALUE_OUT_OF_RANGE",
        "WEIGHTS_NOT_100",
        "DATE_RANGE_INVALID",
        "CHECKSUM_INVALID",
        "EVIDENCE_MISSING",
        "DUPLICATE_CODE",
        "ORPHAN_REFERENCE",
    } <= codes


def test_pr18_validator_reports_required_and_invalid_identifier():
    issues = validate_record(
        {"id": "X", "code": "bad code", "effective_from": "not-a-date"},
        object_type="course",
        required_fields=("code", "name"),
    )
    assert {issue.reason_code for issue in issues} == {
        "REQUIRED_FIELD_MISSING",
        "CODE_INVALID",
        "DATE_INVALID",
    }


@pytest.mark.django_db
def test_pr18_validation_persistence_and_verified_gate(actors):
    _, reviewer, checker, _ = actors
    source = {"records": [{"code": "COURSE-X", "credits": 0}]}
    specs = validate_collection(source["records"], object_type="course")
    run = persist_validation(
        dataset_name="sample-v5",
        source=source,
        issues=specs,
        owner=reviewer,
        actor=actor(reviewer),
    )
    assert run.status == IntegrityValidationRun.Status.BLOCKED
    issue = IntegrityIssue.objects.get(reason_code="CREDITS_OUT_OF_RANGE")
    with pytest.raises(ValidationError, match="diblokir"):
        assert_data_usable(object_type="course", object_id="COURSE-X", purpose="publication")
    issue = transition_issue(
        issue,
        target=IntegrityIssue.Status.INVESTIGATING,
        actor_user=reviewer,
        actor=actor(reviewer),
        authorized=True,
        expected_lock_version=0,
        reason="assigned",
    )
    with pytest.raises(ValidationError, match="stale"):
        transition_issue(
            issue,
            target=IntegrityIssue.Status.RESOLVED,
            actor_user=reviewer,
            actor=actor(reviewer),
            authorized=True,
            expected_lock_version=0,
            reason="fixed",
        )
    issue = transition_issue(
        issue,
        target=IntegrityIssue.Status.RESOLVED,
        actor_user=reviewer,
        actor=actor(reviewer),
        authorized=True,
        expected_lock_version=1,
        reason="source corrected",
    )
    with pytest.raises(ValidationError, match="diblokir"):
        assert_data_usable(object_type="course", object_id="COURSE-X", purpose="attainment")
    transition_issue(
        issue,
        target=IntegrityIssue.Status.VERIFIED,
        actor_user=checker,
        actor=actor(checker),
        authorized=True,
        expected_lock_version=2,
        reason="revalidation passed",
    )
    assert_data_usable(object_type="course", object_id="COURSE-X", purpose="publication")


@pytest.mark.django_db
def test_pr18_persisted_finding_reopens_verified_issue_and_accepted_risk_still_blocks(actors):
    _, reviewer, checker, _ = actors
    source = {"records": [{"code": "COURSE-Y", "credits": 0}]}
    specs = validate_collection(source["records"], object_type="course")
    persist_validation(
        dataset_name="sample-v5",
        source=source,
        issues=specs,
        owner=reviewer,
        actor=actor(reviewer),
    )
    issue = IntegrityIssue.objects.get(object_id="COURSE-Y")
    issue = transition_issue(
        issue,
        target=IntegrityIssue.Status.ACCEPTED_RISK,
        actor_user=reviewer,
        actor=actor(reviewer),
        authorized=True,
        expected_lock_version=0,
        reason="temporary historical exception",
    )
    assert issue.blocks_official_use
    with pytest.raises(ValidationError, match="diblokir"):
        assert_data_usable(object_type="course", object_id="COURSE-Y", purpose="official sync")
    with pytest.raises(PermissionDenied):
        transition_issue(
            issue,
            target=IntegrityIssue.Status.REOPENED,
            actor_user=checker,
            actor=actor(checker),
            authorized=False,
            expected_lock_version=1,
            reason="unauthorized",
        )
