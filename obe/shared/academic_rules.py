from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from obe.shared.models import (
    AcademicAppeal,
    AcademicDecision,
    AcademicRule,
    CohortRulePackage,
    DecisionOverride,
)
from obe.shared.services import ActorContext, record_change

GRADE_RANK = {"E": 0, "D": 1, "C": 2, "BC": 3, "B": 4, "AB": 5, "A": 6}

SAMPLE_RULES = (
    ("ATTENDANCE-UAS-75", "course-enrollment", {"attendancePercent": {"gte": 75}}),
    ("COURSE-PASS-MIN-C", "course-result", {"grade": {"gteRank": "C"}}),
    ("THESIS-PASS-MIN-B", "thesis-result", {"grade": {"gteRank": "B"}}),
    (
        "GRADUATION-144-126-18",
        "student-program",
        {
            "totalEarnedCredits": {"gte": 144},
            "requiredEarnedCredits": {"gte": 126},
            "electiveEarnedCredits": {"gte": 18},
        },
    ),
    ("ENGLISH-MIN-400", "student-program", {"englishScore": {"gte": 400}}),
    (
        "MBKM-ELIGIBILITY",
        "student-program",
        {
            "completedSemesters": {"gte": 4},
            "requiredEarnedCredits": {"gte": 60},
            "activeStatus": True,
            "requiredDECount": 0,
        },
    ),
    (
        "MBKM-CREDIT-CONVERSION",
        "activity",
        {"minutesPerCredit": 2700, "hoursPerCredit": 45},
    ),
    (
        "KKN-ELIGIBILITY-100",
        "student-program",
        {"earnedCredits": {"gte": 100}, "activeStatus": True, "irsRequired": True},
    ),
    (
        "PKL-ELIGIBILITY",
        "student-program",
        {
            "completedSemester": {"gte": 5},
            "activeStatus": True,
            "irsRequired": True,
            "credits": 3,
        },
    ),
    (
        "THESIS-TAKE-ELIGIBILITY",
        "student-program",
        {
            "earnedCredits": {"gte": 120},
            "supportingElectiveCredits": {"gte": 9},
            "methodologyPassed": True,
            "openLab": True,
            "irsRequired": True,
        },
    ),
    (
        "THESIS-EXAM-ELIGIBILITY",
        "thesis",
        {
            "earnedCredits": {"gte": 138},
            "gpa": {"gte": 2},
            "requiredDECount": 0,
            "englishScore": {"gte": 400},
            "guidanceMeetings": {"gte": 9},
            "draftBusinessDaysBefore": {"gte": 7},
        },
    ),
)


def sample_rule_registry() -> dict[str, Any]:
    def grade_rows(rows):
        result = []
        for index, (minimum, grade, point) in enumerate(rows):
            maximum = 100 if index == 0 else Decimal(str(rows[index - 1][0])) - Decimal("0.01")
            result.append(
                {
                    "grade": grade,
                    "min": minimum,
                    "max": float(maximum),
                    "gradePoint": point,
                }
            )
        return result

    from obe.shared.rules import CURRENT, LEGACY

    return {
        "rulePackages": [
            {
                "id": "LEGACY-ABCDE-V1",
                "code": "LEGACY-ABCDE",
                "version": 1,
                "cohortFrom": 2020,
                "cohortTo": 2023,
                "effectiveFrom": "2020-08-01",
                "effectiveTo": "2024-07-31",
                "gradeScheme": grade_rows(LEGACY),
                "minimumPassingGrade": "C",
                "minimumThesisGrade": "B",
                "progressMilestones": [
                    {"timing": "end-semester", "semester": semester} for semester in (3, 7, 14)
                ],
            },
            {
                "id": "CURRENT-AABBC-V1",
                "code": "CURRENT-AABBC",
                "version": 1,
                "cohortFrom": 2024,
                "cohortTo": None,
                "effectiveFrom": "2024-08-01",
                "effectiveTo": None,
                "gradeScheme": grade_rows(CURRENT),
                "minimumPassingGrade": "C",
                "minimumThesisGrade": "B",
                "irsPolicy": {
                    "semester1MaxCredits": 20,
                    "semester2DefaultMaxCredits": 20,
                    "semester2MaxCreditsWhenPreviousGpaBelow2": 18,
                    "semester3PlusBands": [
                        {"previousGpaMin": 0, "previousGpaMaxExclusive": 2, "maxCredits": 18},
                        {"previousGpaMin": 2, "previousGpaMaxExclusive": 2.5, "maxCredits": 20},
                        {"previousGpaMin": 2.5, "previousGpaMaxExclusive": 3, "maxCredits": 22},
                        {"previousGpaMin": 3, "previousGpaMaxExclusive": 4.01, "maxCredits": 24},
                    ],
                    "returnFromLeaveMaxCredits": 18,
                },
                "progressMilestones": [
                    {
                        "timing": "start-semester",
                        "semester": semester,
                        "minimumEarnedCredits": credits,
                        "minimumGpa": 2.5,
                    }
                    for semester, credits in ((3, 25), (5, 50), (13, 108))
                ],
            },
        ],
        "rules": [
            {
                "code": code,
                "version": 1,
                "scope": scope,
                "severity": "blocking",
                "expression": expression,
                "effectiveFrom": "2024-08-01"
                if code
                not in {
                    "ATTENDANCE-UAS-75",
                    "COURSE-PASS-MIN-C",
                    "THESIS-PASS-MIN-B",
                    "GRADUATION-144-126-18",
                    "ENGLISH-MIN-400",
                }
                else "2020-08-01",
                "status": "active",
            }
            for code, scope, expression in SAMPLE_RULES
        ],
    }


@dataclass(frozen=True)
class RuleEvaluation:
    outcome: str
    reason_code: str
    evidence_rows: tuple[dict[str, Any], ...]
    input_snapshot: dict[str, Any]
    calculation_trace: tuple[str, ...]
    explanation: str
    input_hash: str
    decision_hash: str


def _normalized(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    if isinstance(value, dict):
        return {str(key): _normalized(value[key]) for key in sorted(value)}
    if isinstance(value, list | tuple):
        return [_normalized(item) for item in value]
    return value


def _canonical(value: Any) -> str:
    return json.dumps(_normalized(value), sort_keys=True, separators=(",", ":"), default=str)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _decimal(value: Any) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise InvalidOperation
    return Decimal(str(value))


def _condition_passes(actual: Any, condition: Any) -> tuple[bool, str]:
    if not isinstance(condition, dict):
        passed = actual == condition
        return passed, f"eq {condition!r}"
    checks: list[bool] = []
    descriptions: list[str] = []
    for operator in sorted(condition):
        expected = condition[operator]
        try:
            if operator == "gte":
                passed = _decimal(actual) >= _decimal(expected)
            elif operator == "gt":
                passed = _decimal(actual) > _decimal(expected)
            elif operator == "lte":
                passed = _decimal(actual) <= _decimal(expected)
            elif operator == "lt":
                passed = _decimal(actual) < _decimal(expected)
            elif operator == "eq":
                passed = actual == expected
            elif operator == "in":
                passed = actual in expected
            elif operator == "gteRank":
                passed = GRADE_RANK.get(str(actual), -1) >= GRADE_RANK.get(str(expected), 999)
            else:
                raise ValidationError(f"Operator rule tidak didukung: {operator}")
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValidationError(f"Nilai tidak sesuai operator {operator}") from exc
        checks.append(passed)
        descriptions.append(f"{operator} {expected!r}")
    return all(checks), " and ".join(descriptions)


def evaluate_rule(
    rule: AcademicRule,
    inputs: dict[str, Any],
    *,
    object_type: str,
    object_id: str,
    source_versions: dict[str, Any] | None = None,
) -> RuleEvaluation:
    if rule.status != AcademicRule.Status.ACTIVE:
        raise ValidationError("Hanya rule aktif yang dapat dievaluasi")
    required = tuple(rule.input_schema.get("required", rule.input_schema.keys()))
    missing = sorted(field for field in required if field not in inputs or inputs[field] is None)
    snapshot = _normalized(inputs)
    input_hash = _fingerprint(snapshot)
    evidence: list[dict[str, Any]] = []
    trace: list[str] = [f"rule={rule.code}@{rule.version}", f"input={input_hash}"]
    if missing:
        outcome = str(AcademicDecision.Outcome.INDETERMINATE)
        reason_code = f"{rule.code}_INPUT_MISSING"
        trace.append(f"missing={','.join(missing)}")
        explanation = f"Input wajib belum tersedia: {', '.join(missing)}."
    else:
        failed: list[str] = []
        for field in sorted(rule.expression):
            if field not in inputs:
                missing.append(field)
                continue
            passed, condition = _condition_passes(inputs[field], rule.expression[field])
            row = {
                "field": field,
                "actual": _normalized(inputs[field]),
                "condition": condition,
                "passed": passed,
                "source_version": (source_versions or {}).get(field, ""),
            }
            evidence.append(row)
            trace.append(f"{field}:{condition}:{'pass' if passed else 'fail'}")
            if not passed:
                failed.append(field)
        if missing:
            outcome = str(AcademicDecision.Outcome.INDETERMINATE)
            reason_code = f"{rule.code}_INPUT_MISSING"
            trace.append(f"missing={','.join(sorted(missing))}")
            explanation = f"Input ekspresi belum tersedia: {', '.join(sorted(missing))}."
        elif failed:
            outcome = str(AcademicDecision.Outcome.FAIL)
            reason_code = f"{rule.code}_FAIL"
            explanation = (
                f"Rule {rule.code} versi {rule.version} gagal pada: {', '.join(failed)}. "
                "Periksa sumber data pada evidence rows sebelum melakukan koreksi atau banding."
            )
        else:
            outcome = str(AcademicDecision.Outcome.PASS)
            reason_code = f"{rule.code}_PASS"
            explanation = f"Seluruh kondisi rule {rule.code} versi {rule.version} terpenuhi."
    decision_hash = _fingerprint(
        {
            "object_type": object_type,
            "object_id": object_id,
            "rule": rule.code,
            "rule_version": rule.version,
            "inputs": snapshot,
            "outcome": outcome,
            "reason_code": reason_code,
            "evidence": evidence,
            "trace": trace,
        }
    )
    return RuleEvaluation(
        outcome,
        reason_code,
        tuple(evidence),
        snapshot,
        tuple(trace),
        explanation,
        input_hash,
        decision_hash,
    )


@transaction.atomic
def evaluate_and_record(
    rule: AcademicRule,
    inputs: dict[str, Any],
    *,
    object_type: str,
    object_id: str,
    actor: ActorContext,
    package: CohortRulePackage | None = None,
    source_versions: dict[str, Any] | None = None,
) -> AcademicDecision:
    evaluation = evaluate_rule(
        rule,
        inputs,
        object_type=object_type,
        object_id=object_id,
        source_versions=source_versions,
    )
    decision = AcademicDecision.objects.filter(decision_hash=evaluation.decision_hash).first()
    if decision:
        return decision
    decision = AcademicDecision.objects.create(
        object_type=object_type,
        object_id=object_id,
        rule=rule,
        package=package,
        outcome=evaluation.outcome,
        reason_code=evaluation.reason_code,
        evidence_rows=list(evaluation.evidence_rows),
        input_snapshot=evaluation.input_snapshot,
        calculation_trace=list(evaluation.calculation_trace),
        source_versions=source_versions or {},
        explanation=evaluation.explanation,
        input_hash=evaluation.input_hash,
        decision_hash=evaluation.decision_hash,
        correlation_id=actor.correlation_id,
    )
    record_change(
        actor=actor,
        action="rule.evaluated",
        object_type="academic-decision",
        object_id=str(decision.id),
        summary=evaluation.explanation,
        after={"outcome": decision.outcome, "reason_code": decision.reason_code},
        reason="Evaluasi deterministik menggunakan rule dan input snapshot berversi",
        references=((object_type, object_id, "decision source"),),
    )
    return decision


def replay_decision(decision: AcademicDecision) -> RuleEvaluation:
    replay = evaluate_rule(
        decision.rule,
        decision.input_snapshot,
        object_type=decision.object_type,
        object_id=decision.object_id,
        source_versions=decision.source_versions,
    )
    if replay.decision_hash != decision.decision_hash:
        raise ValidationError(
            "Replay decision tidak identik; snapshot atau rule terindikasi berubah"
        )
    return replay


def resolve_rule_package(*, cohort: int, on_date: date | None = None) -> CohortRulePackage:
    on_date = on_date or timezone.localdate()
    matches = (
        CohortRulePackage.objects.filter(
            status=CohortRulePackage.Status.ACTIVE,
            cohort_from__lte=cohort,
            effective_from__lte=on_date,
        )
        .filter(Q(cohort_to__isnull=True) | Q(cohort_to__gte=cohort))
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=on_date))
    )
    count = matches.count()
    if count != 1:
        raise ValidationError(
            "Mahasiswa harus memiliki tepat satu package aktif; "
            f"ditemukan {count} untuk cohort {cohort}"
        )
    return matches.get()


def select_active_rule(
    *, code: str, scope: str, cohort: int, on_date: date | None = None
) -> AcademicRule:
    on_date = on_date or timezone.localdate()
    matches = list(
        AcademicRule.objects.filter(
            code=code,
            status=AcademicRule.Status.ACTIVE,
            effective_from__lte=on_date,
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=on_date))
        .order_by("priority", "-version")
    )
    matches = [
        rule
        for rule in matches
        if rule.scope.get("type", rule.scope.get("scope", "")) == scope
        and (not rule.cohort or int(rule.cohort.split("-")[0]) <= cohort)
    ]
    if not matches:
        raise AcademicRule.DoesNotExist(code)
    if len(matches) > 1 and matches[0].priority == matches[1].priority:
        raise ValidationError("Priority conflict pada rule aktif")
    return matches[0]


@transaction.atomic
def review_rule(rule: AcademicRule, *, reviewer, actor: ActorContext, note: str) -> AcademicRule:
    locked = AcademicRule.objects.select_for_update().get(pk=rule.pk)
    if locked.status != AcademicRule.Status.DRAFT:
        raise ValidationError("Hanya rule draft yang dapat direview")
    if reviewer.pk == locked.created_by_id:
        raise ValidationError("Pembuat rule tidak boleh mereview sendiri")
    locked.status = AcademicRule.Status.REVIEWED
    locked.reviewed_by = reviewer
    locked.review_note = note
    locked.save()
    record_change(
        actor=actor,
        action="rule.reviewed",
        object_type="academic-rule",
        object_id=f"{locked.code}@{locked.version}",
        summary="Rule direview",
        after={"status": locked.status},
        reason=note,
    )
    return locked


@transaction.atomic
def activate_rule(
    rule: AcademicRule,
    *,
    checker,
    actor: ActorContext,
    reason: str,
) -> AcademicRule:
    locked = AcademicRule.objects.select_for_update().get(pk=rule.pk)
    if locked.status != AcademicRule.Status.REVIEWED:
        raise ValidationError("Hanya rule reviewed yang dapat diaktifkan")
    if checker.pk == locked.created_by_id:
        raise ValidationError("Maker dan checker rule harus berbeda")
    active = AcademicRule.objects.select_for_update().filter(
        code=locked.code,
        status=AcademicRule.Status.ACTIVE,
    )
    for previous in active:
        previous.status = AcademicRule.Status.RETIRED
        previous.save(update_fields=["status", "updated_at"])
    locked.status = AcademicRule.Status.ACTIVE
    locked.activated_by = checker
    locked.activated_at = timezone.now()
    locked.save()
    record_change(
        actor=actor,
        action="rule.activated",
        object_type="academic-rule",
        object_id=f"{locked.code}@{locked.version}",
        summary="Rule diaktifkan melalui maker-checker",
        after={"status": locked.status},
        reason=reason,
    )
    return locked


@transaction.atomic
def request_override(
    decision: AcademicDecision,
    *,
    maker,
    actor: ActorContext,
    authorized: bool,
    reason_code: str,
    reason: str,
    evidence_documents: list[dict[str, Any]],
    impact: str,
    valid_to=None,
) -> DecisionOverride:
    if not authorized:
        raise PermissionDenied("Actor tidak berwenang membuat override")
    if decision.outcome != AcademicDecision.Outcome.FAIL:
        raise ValidationError("Override hanya berlaku pada keputusan gagal")
    override = DecisionOverride(
        decision=decision,
        maker=maker,
        reason_code=reason_code,
        reason=reason,
        evidence_documents=evidence_documents,
        impact=impact,
        valid_to=valid_to,
    )
    override.full_clean()
    override.save()
    record_change(
        actor=actor,
        action="override.submitted",
        object_type="decision-override",
        object_id=str(override.id),
        summary="Override keputusan diajukan tanpa mengubah data sumber",
        after={"decision": str(decision.id), "status": override.status},
        reason=reason,
        references=(("academic-decision", str(decision.id), "overridden decision"),),
    )
    return override


@transaction.atomic
def decide_override(
    override: DecisionOverride,
    *,
    checker,
    actor: ActorContext,
    authorized: bool,
    approve: bool,
    note: str,
) -> DecisionOverride:
    if not authorized:
        raise PermissionDenied("Actor tidak berwenang memutus override")
    locked = DecisionOverride.objects.select_for_update().get(pk=override.pk)
    if locked.status not in {DecisionOverride.Status.SUBMITTED, DecisionOverride.Status.REVIEWED}:
        raise ValidationError("Override tidak berada pada status yang dapat diputus")
    if locked.maker_id == checker.pk:
        raise ValidationError("Maker tidak boleh menyetujui override sendiri")
    locked.checker = checker
    locked.status = (
        DecisionOverride.Status.APPROVED if approve else DecisionOverride.Status.REJECTED
    )
    locked.review_note = note
    locked.decided_at = timezone.now()
    locked.full_clean()
    locked.save()
    record_change(
        actor=actor,
        action=f"override.{locked.status}",
        object_type="decision-override",
        object_id=str(locked.id),
        summary=f"Override {locked.status}",
        after={"status": locked.status, "checker": str(checker.pk)},
        reason=note,
        references=(("academic-decision", str(locked.decision_id), "source decision"),),
    )
    return locked


def effective_outcome(decision: AcademicDecision, *, at=None) -> str:
    at = at or timezone.now()
    approved = decision.overrides.filter(
        status=DecisionOverride.Status.APPROVED,
        valid_from__lte=at,
    ).filter(Q(valid_to__isnull=True) | Q(valid_to__gt=at))
    return "overridden" if approved.exists() else decision.outcome


@transaction.atomic
def submit_appeal(
    decision: AcademicDecision,
    *,
    submitted_by,
    statement: str,
    evidence_documents: list[dict[str, Any]],
    expires_at,
    actor: ActorContext,
) -> AcademicAppeal:
    if expires_at <= timezone.now():
        raise ValidationError("Masa banding harus berada di masa depan")
    appeal = AcademicAppeal(
        decision=decision,
        submitted_by=submitted_by,
        statement=statement,
        evidence_documents=evidence_documents,
        expires_at=expires_at,
    )
    appeal.full_clean()
    appeal.save()
    record_change(
        actor=actor,
        action="appeal.submitted",
        object_type="academic-appeal",
        object_id=str(appeal.id),
        summary="Banding keputusan diajukan",
        after={"decision": str(decision.id), "status": appeal.status},
        references=(("academic-decision", str(decision.id), "appealed decision"),),
    )
    return appeal


APPEAL_TRANSITIONS = {
    AcademicAppeal.Status.SUBMITTED: {
        AcademicAppeal.Status.REVIEWED,
        AcademicAppeal.Status.INFORMATION_NEEDED,
        AcademicAppeal.Status.EXPIRED,
    },
    AcademicAppeal.Status.INFORMATION_NEEDED: {
        AcademicAppeal.Status.REVIEWED,
        AcademicAppeal.Status.EXPIRED,
    },
    AcademicAppeal.Status.REVIEWED: {
        AcademicAppeal.Status.APPROVED,
        AcademicAppeal.Status.REJECTED,
    },
    AcademicAppeal.Status.APPROVED: {AcademicAppeal.Status.CLOSED},
    AcademicAppeal.Status.REJECTED: {AcademicAppeal.Status.CLOSED},
}


@transaction.atomic
def transition_appeal(
    appeal: AcademicAppeal,
    *,
    reviewer,
    actor: ActorContext,
    target: str,
    note: str,
) -> AcademicAppeal:
    locked = AcademicAppeal.objects.select_for_update().get(pk=appeal.pk)
    if timezone.now() >= locked.expires_at and target != AcademicAppeal.Status.EXPIRED:
        raise ValidationError("Banding sudah kedaluwarsa")
    if target not in APPEAL_TRANSITIONS.get(locked.status, set()):
        raise ValidationError(f"Transisi banding {locked.status} → {target} tidak valid")
    if reviewer.pk == locked.submitted_by_id:
        raise ValidationError("Pemohon banding tidak boleh menjadi reviewer")
    locked.reviewed_by = reviewer
    locked.status = target
    if target == AcademicAppeal.Status.INFORMATION_NEEDED:
        locked.information_request = note
    else:
        locked.resolution = note
    if target == AcademicAppeal.Status.CLOSED:
        locked.closed_at = timezone.now()
    locked.full_clean()
    locked.save()
    record_change(
        actor=actor,
        action=f"appeal.{target}",
        object_type="academic-appeal",
        object_id=str(locked.id),
        summary=f"Status banding menjadi {target}",
        after={"status": target},
        reason=note,
        references=(("academic-decision", str(locked.decision_id), "appealed decision"),),
    )
    return locked
