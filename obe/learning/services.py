from __future__ import annotations

import hashlib
import json
from datetime import date
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from obe.learning.models import (
    Attendance,
    CourseOutcome,
    PerformanceIndicator,
    RPSFieldComment,
    RPSVersion,
    SubOutcome,
    WeeklyPlan,
)
from obe.shared.services import ActorContext, record_change

SUPPORTED_METHODS = {
    "lecture",
    "discussion",
    "collaborative-learning",
    "problem-based-learning",
    "project-based-learning",
    "case-based-learning",
    "practice",
    "tutorial",
    "seminar",
    "other",
}


def _actor(user, scope: str = "rps") -> ActorContext:
    return ActorContext(str(user.pk), user.get_username(), scope)


def attendance_eligibility(*, offering_id: int, student_id: str) -> dict:
    rows = Attendance.objects.filter(offering_id=offering_id, student_id=student_id)
    counted = rows.exclude(status__in=["cancelled", "exempt"])
    denominator = counted.count()
    attended = counted.filter(status__in=["present", "late", "permit", "sick"]).count()
    percent = Decimal("0") if denominator == 0 else Decimal(attended * 100) / denominator
    return {
        "eligible": denominator > 0 and percent >= Decimal("75"),
        "percent": percent.quantize(Decimal("0.01")),
        "attended": attended,
        "denominator": denominator,
        "reason_code": "ATTENDANCE_OK" if percent >= 75 else "ATTENDANCE_BELOW_75",
    }


def rps_payload(rps: RPSVersion) -> dict[str, Any]:
    return {
        "public_id": str(rps.public_id),
        "version": rps.version,
        "offering": str(rps.offering.public_id),
        "content": rps.content,
        "assessment_weight": str(rps.total_assessment_weight),
        "course_outcomes": [
            {
                "code": row.code,
                "description": row.description,
                "bloom": row.bloom_level,
                "target": str(row.target),
                "weight": str(row.weight),
                "program_cpmk_ids": row.program_cpmk_ids,
                "cpl_ids": row.cpl_ids,
            }
            for row in rps.course_outcomes.order_by("order", "code")
        ],
        "sub_outcomes": [
            {
                "course_outcome": row.course_outcome.code,
                "code": row.code,
                "description": row.description,
                "bloom": row.bloom_level,
                "target": str(row.target),
                "weight": str(row.weight),
            }
            for row in rps.sub_outcomes.select_related("course_outcome").order_by("order", "code")
        ],
        "indicators": [
            {
                "sub_outcome": row.sub_outcome.code,
                "code": row.code,
                "description": row.description,
                "measurement": row.measurement,
                "target": str(row.target),
                "observable": row.observable,
            }
            for row in rps.indicators.select_related("sub_outcome").order_by("order", "code")
        ],
        "weekly_plans": [
            {
                "week": row.week,
                "meeting_type": row.meeting_type,
                "outcomes": row.outcomes,
                "indicators": row.indicators,
                "material": row.material,
                "methods": row.methods,
                "activities": row.activities,
                "assignment": row.assignment,
                "contact_minutes": row.contact_minutes,
                "structured_minutes": row.structured_minutes,
                "independent_minutes": row.independent_minutes,
                "planned_date": row.planned_date.isoformat() if row.planned_date else None,
            }
            for row in rps.weekly_plans.order_by("week")
        ],
    }


def rps_checksum(rps: RPSVersion) -> str:
    canonical = json.dumps(rps_payload(rps), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _add(errors: list[dict], code: str, detail: str, path: str = "") -> None:
    errors.append({"code": code, "detail": detail, "path": path})


def validate_rps(rps: RPSVersion) -> dict[str, Any]:
    errors: list[dict] = []
    required_content = ("references", "learning_materials")
    for field in required_content:
        if not rps.content.get(field):
            _add(errors, "RPS_REQUIRED_FIELD_MISSING", f"{field} wajib", f"content.{field}")

    outcomes = list(rps.course_outcomes.all())
    if not outcomes:
        _add(errors, "COURSE_OUTCOME_MISSING", "Minimal satu CPMK-RPS wajib")
    if sum((row.weight for row in outcomes), Decimal("0")) != Decimal("100"):
        _add(errors, "COURSE_OUTCOME_WEIGHT_NOT_100", "Total bobot CPMK-RPS harus 100")
    for outcome in outcomes:
        if not outcome.program_cpmk_ids or not outcome.cpl_ids:
            _add(errors, "COURSE_OUTCOME_MAPPING_BROKEN", outcome.code, outcome.code)
        children = list(outcome.sub_outcomes.all())
        if not children:
            _add(errors, "SUB_OUTCOME_MISSING", outcome.code, outcome.code)
        if sum((row.weight for row in children), Decimal("0")) != Decimal("100"):
            _add(errors, "SUB_OUTCOME_WEIGHT_NOT_100", outcome.code, outcome.code)
        for child in children:
            indicators = list(child.indicators.all())
            if not indicators:
                _add(errors, "INDICATOR_MISSING", child.code, child.code)
            if any(not row.observable or not row.description.strip() for row in indicators):
                _add(errors, "INDICATOR_NOT_OBSERVABLE", child.code, child.code)

    weeks = {row.week: row for row in rps.weekly_plans.all()}
    if set(weeks) != set(range(1, 17)):
        _add(errors, "WEEKLY_PLAN_NOT_16", "RPS reguler wajib memuat minggu 1–16")
    if 8 not in weeks or weeks[8].meeting_type != "midterm":
        _add(errors, "MIDTERM_WEEK_MISSING", "Minggu 8 harus UTS", "weekly_plans.8")
    if 16 not in weeks or weeks[16].meeting_type != "final":
        _add(errors, "FINAL_WEEK_MISSING", "Minggu 16 harus UAS", "weekly_plans.16")
    for week, row in weeks.items():
        if row.meeting_type == "regular":
            unsupported = set(row.methods) - SUPPORTED_METHODS
            if not row.methods or unsupported:
                _add(errors, "LEARNING_METHOD_INVALID", f"Minggu {week}: {sorted(unsupported)}")
            if min(row.contact_minutes, row.structured_minutes, row.independent_minutes) <= 0:
                _add(errors, "LEARNING_TIME_INVALID", f"Minggu {week}")
        offering = rps.offering
        if row.planned_date and offering.starts_on and offering.ends_on:
            if not offering.starts_on <= row.planned_date <= offering.ends_on:
                _add(errors, "WEEK_DATE_OUTSIDE_SEMESTER", f"Minggu {week}")

    assessments = rps.content.get("assessment_snapshot", [])
    if not assessments:
        _add(errors, "ASSESSMENT_PLAN_MISSING", "Snapshot rencana asesmen wajib")
    total = sum((Decimal(str(item.get("weight", 0))) for item in assessments), Decimal("0"))
    if total != Decimal("100") or rps.total_assessment_weight != Decimal("100"):
        _add(errors, "ASSESSMENT_WEIGHT_NOT_100", f"Total ditemukan {total}")
    mapped_indicators: set[str] = set()
    for item in assessments:
        if item.get("status") != "published" or not item.get("published_before_teaching"):
            _add(errors, "ASSESSMENT_NOT_PUBLISHED_BEFORE_TEACHING", item.get("code", "?"))
        for mapping in item.get("mappings", []):
            mapped_indicators.update(
                mapping.get("indicator_codes", mapping.get("indicatorCodes", []))
            )
    expected_indicators = set(rps.indicators.values_list("code", flat=True))
    missing_indicators = sorted(expected_indicators - mapped_indicators)
    if missing_indicators:
        _add(errors, "ASSESSMENT_MAPPING_INCOMPLETE", ", ".join(missing_indicators))
    return {"valid": not errors, "errors": errors, "checksum": rps_checksum(rps)}


def generate_outcome_code(rps: RPSVersion, *, prefix: str = "CPMK") -> str:
    used = set(rps.course_outcomes.values_list("code", flat=True))
    number = 1
    while f"{prefix}-{number:02d}" in used:
        number += 1
    return f"{prefix}-{number:02d}"


@transaction.atomic
def bulk_map_course_outcomes(
    rps: RPSVersion, *, mappings: dict[str, dict[str, list[str]]], user
) -> RPSVersion:
    if rps.status not in {RPSVersion.Status.DRAFT, RPSVersion.Status.RETURNED}:
        raise ValidationError("Bulk mapping hanya dapat dilakukan pada RPS editable")
    outcomes = {row.code: row for row in rps.course_outcomes.all()}
    if unknown := set(mappings) - set(outcomes):
        raise ValidationError(f"Kode CPMK-RPS tidak dikenal: {', '.join(sorted(unknown))}")
    history = []
    for code, values in mappings.items():
        program_ids = values.get("program_cpmk_ids", [])
        cpl_ids = values.get("cpl_ids", [])
        if not program_ids or not cpl_ids:
            raise ValidationError(f"Mapping {code} wajib memiliki CPMK program dan CPL")
        outcome = outcomes[code]
        history.append(
            {
                "code": code,
                "program_cpmk_ids": outcome.program_cpmk_ids,
                "cpl_ids": outcome.cpl_ids,
                "changed_at": timezone.now().isoformat(),
                "changed_by": str(user.pk),
            }
        )
        outcome.program_cpmk_ids = program_ids
        outcome.cpl_ids = cpl_ids
        outcome.updated_by_actor_id = str(user.pk)
        outcome.full_clean()
        outcome.save(
            update_fields=["program_cpmk_ids", "cpl_ids", "updated_by_actor_id", "updated_at"]
        )
    rps.content = {
        **rps.content,
        "mapping_history": [*rps.content.get("mapping_history", []), *history],
    }
    rps.reviewed_checksum = ""
    rps.approved_checksum = ""
    rps.save(update_fields=["content", "reviewed_checksum", "approved_checksum", "updated_at"])
    return rps


def _assert_lock(rps: RPSVersion, expected_lock_version: int | None) -> None:
    if expected_lock_version is not None and rps.lock_version != expected_lock_version:
        raise ValidationError("Optimistic lock conflict; review dilakukan pada versi lama")


def _save_state(rps: RPSVersion, fields: list[str]) -> RPSVersion:
    rps.lock_version += 1
    rps.save(update_fields=[*fields, "lock_version", "updated_at"])
    return rps


@transaction.atomic
def submit_rps_for_review(
    rps: RPSVersion, *, user, expected_lock_version: int | None = None
) -> RPSVersion:
    rps = RPSVersion.objects.select_for_update().get(pk=rps.pk)
    _assert_lock(rps, expected_lock_version)
    if rps.status not in {RPSVersion.Status.DRAFT, RPSVersion.Status.RETURNED}:
        raise ValidationError("Hanya RPS draft/returned yang dapat diajukan")
    report = validate_rps(rps)
    if not report["valid"]:
        raise ValidationError({"rps": report["errors"]})
    rps.status = RPSVersion.Status.GPM_REVIEW
    rps.content_checksum = report["checksum"]
    rps.returned_comment = ""
    _save_state(rps, ["status", "content_checksum", "returned_comment"])
    record_change(
        actor=_actor(user),
        action="rps.submit",
        object_type="rps",
        object_id=str(rps.public_id),
        summary="RPS diajukan ke review GPM",
        after={"checksum": report["checksum"]},
    )
    return rps


@transaction.atomic
def review_rps(rps: RPSVersion, *, user, expected_lock_version: int | None = None) -> RPSVersion:
    rps = RPSVersion.objects.select_for_update().get(pk=rps.pk)
    _assert_lock(rps, expected_lock_version)
    if rps.status != RPSVersion.Status.GPM_REVIEW:
        raise ValidationError("RPS tidak berada pada tahap review GPM")
    if user.pk == rps.authored_by_id:
        raise ValidationError("Author tidak boleh mereview RPS sendiri")
    checksum = rps_checksum(rps)
    if checksum != rps.content_checksum:
        raise ValidationError("Konten berubah selama review; ajukan ulang")
    rps.status = RPSVersion.Status.PRODI_APPROVAL
    rps.reviewed_by = user
    rps.reviewed_checksum = checksum
    rps.reviewed_at = timezone.now()
    _save_state(rps, ["status", "reviewed_by", "reviewed_checksum", "reviewed_at"])
    record_change(
        actor=_actor(user),
        action="rps.review",
        object_type="rps",
        object_id=str(rps.public_id),
        summary="RPS lolos review GPM",
        after={"checksum": checksum},
    )
    return rps


@transaction.atomic
def approve_rps(rps: RPSVersion, *, user, expected_lock_version: int | None = None) -> RPSVersion:
    rps = RPSVersion.objects.select_for_update().get(pk=rps.pk)
    _assert_lock(rps, expected_lock_version)
    if rps.status != RPSVersion.Status.PRODI_APPROVAL:
        raise ValidationError("RPS tidak berada pada tahap approval Prodi")
    if user.pk in {rps.authored_by_id, rps.reviewed_by_id}:
        raise ValidationError("Maker, reviewer, dan approver harus berbeda")
    checksum = rps_checksum(rps)
    if checksum != rps.reviewed_checksum:
        raise ValidationError("Approval stale; konten berubah setelah review")
    rps.approved_by = user
    rps.approved_checksum = checksum
    rps.approved_at = timezone.now()
    _save_state(rps, ["approved_by", "approved_checksum", "approved_at"])
    record_change(
        actor=_actor(user),
        action="approval.rps",
        object_type="rps",
        object_id=str(rps.public_id),
        summary="RPS disetujui Prodi",
        after={"checksum": checksum},
        reason="RPS valid dan terulas",
    )
    return rps


@transaction.atomic
def return_rps(
    rps: RPSVersion,
    *,
    user,
    comment: str,
    field_path: str = "content",
    expected_lock_version: int | None = None,
) -> RPSVersion:
    if not comment.strip():
        raise ValidationError("Komentar pengembalian wajib")
    rps = RPSVersion.objects.select_for_update().get(pk=rps.pk)
    _assert_lock(rps, expected_lock_version)
    if rps.status not in {RPSVersion.Status.GPM_REVIEW, RPSVersion.Status.PRODI_APPROVAL}:
        raise ValidationError("RPS tidak sedang direview/disetujui")
    RPSFieldComment.objects.create(rps=rps, field_path=field_path, comment=comment, author=user)
    rps.status = RPSVersion.Status.RETURNED
    rps.returned_comment = comment
    rps.reviewed_checksum = ""
    rps.approved_checksum = ""
    rps.approved_by = None
    _save_state(
        rps,
        ["status", "returned_comment", "reviewed_checksum", "approved_checksum", "approved_by"],
    )
    return rps


@transaction.atomic
def publish_rps(rps: RPSVersion, *, user=None, strict: bool = False) -> RPSVersion:
    rps = RPSVersion.objects.select_for_update().get(pk=rps.pk)
    checksum = rps_checksum(rps)
    if strict:
        report = validate_rps(rps)
        if not report["valid"]:
            raise ValidationError({"rps": report["errors"]})
        if rps.status != RPSVersion.Status.PRODI_APPROVAL or not rps.approved_by_id:
            raise ValidationError("RPS harus disetujui Prodi sebelum published")
        if checksum != rps.reviewed_checksum or checksum != rps.approved_checksum:
            raise ValidationError("Approval stale; snapshot tidak replayable")
    else:
        rps.content_checksum = checksum
        rps.reviewed_checksum = checksum
        rps.approved_checksum = checksum
    rps.status = RPSVersion.Status.PUBLISHED
    rps.published_at = timezone.now()
    rps.approval_snapshot = {
        "version": rps.version,
        "reviewer": rps.reviewed_by_id,
        "approver": rps.approved_by_id,
        "weight": str(rps.total_assessment_weight),
        "checksum": checksum,
        "payload": rps_payload(rps),
    }
    rps.full_clean()
    rps.lock_version += 1
    rps.save(
        update_fields=[
            "status",
            "published_at",
            "content_checksum",
            "reviewed_checksum",
            "approved_checksum",
            "approval_snapshot",
            "lock_version",
            "updated_at",
        ]
    )
    if user:
        record_change(
            actor=_actor(user),
            action="approval.rps.publish",
            object_type="rps",
            object_id=str(rps.public_id),
            summary="RPS immutable dipublikasikan",
            after={"checksum": checksum, "version": rps.version},
            reason="Approval lengkap",
            event_type="learning.rps.published",
            aggregate_version=rps.version,
        )
    return rps


@transaction.atomic
def clone_rps(
    source: RPSVersion, *, user, revision_reason: str, effective_from: date | None = None
) -> RPSVersion:
    source = RPSVersion.objects.get(pk=source.pk)
    if source.status != RPSVersion.Status.PUBLISHED or not revision_reason.strip():
        raise ValidationError("Clone versi membutuhkan RPS published dan alasan revisi")
    version = (
        RPSVersion.objects.filter(offering=source.offering).order_by("-version").first().version + 1
    )
    clone = RPSVersion.objects.create(
        offering=source.offering,
        version=version,
        effective_from=effective_from,
        content=source.content,
        total_assessment_weight=source.total_assessment_weight,
        authored_by=user,
        revision_reason=revision_reason,
        created_by_actor_id=str(user.pk),
        updated_by_actor_id=str(user.pk),
    )
    outcome_map = {}
    for row in source.course_outcomes.order_by("order"):
        outcome_map[row.pk] = CourseOutcome.objects.create(
            rps=clone,
            code=row.code,
            description=row.description,
            bloom_level=row.bloom_level,
            target=row.target,
            weight=row.weight,
            order=row.order,
            program_cpmk_ids=row.program_cpmk_ids,
            cpl_ids=row.cpl_ids,
            status=row.status,
        )
    sub_map = {}
    for row in source.sub_outcomes.order_by("order"):
        sub_map[row.pk] = SubOutcome.objects.create(
            rps=clone,
            course_outcome=outcome_map[row.course_outcome_id],
            code=row.code,
            description=row.description,
            bloom_level=row.bloom_level,
            target=row.target,
            weight=row.weight,
            order=row.order,
            status=row.status,
        )
    for row in source.indicators.order_by("order"):
        PerformanceIndicator.objects.create(
            rps=clone,
            sub_outcome=sub_map[row.sub_outcome_id],
            code=row.code,
            description=row.description,
            measurement=row.measurement,
            target=row.target,
            observable=row.observable,
            order=row.order,
            status=row.status,
        )
    for row in source.weekly_plans.order_by("week"):
        WeeklyPlan.objects.create(
            rps=clone,
            week=row.week,
            meeting_type=row.meeting_type,
            outcomes=row.outcomes,
            indicators=row.indicators,
            material=row.material,
            methods=row.methods,
            activities=row.activities,
            assignment=row.assignment,
            contact_minutes=row.contact_minutes,
            structured_minutes=row.structured_minutes,
            independent_minutes=row.independent_minutes,
            planned_date=row.planned_date,
        )
    return clone


def rollback_rps(current: RPSVersion, previous: RPSVersion, *, user, reason: str) -> RPSVersion:
    if current.offering_id != previous.offering_id:
        raise ValidationError("Rollback hanya boleh pada offering yang sama")
    if (
        current.status != RPSVersion.Status.PUBLISHED
        or previous.status != RPSVersion.Status.PUBLISHED
    ):
        raise ValidationError("Rollback membutuhkan dua snapshot published")
    return clone_rps(
        previous,
        user=user,
        revision_reason=f"Rollback dari v{current.version} ke v{previous.version}: {reason}",
    )


def rps_diff(left: RPSVersion, right: RPSVersion) -> dict[str, Any]:
    left_payload, right_payload = rps_payload(left), rps_payload(right)
    keys = sorted(set(left_payload) | set(right_payload))
    changed = {
        key: {"before": left_payload.get(key), "after": right_payload.get(key)}
        for key in keys
        if left_payload.get(key) != right_payload.get(key)
    }
    return {"changed": changed, "same": not changed}


@transaction.atomic
def reschedule_week(plan: WeeklyPlan, *, user, new_date: date, reason: str) -> WeeklyPlan:
    if not reason.strip() or plan.rps.status != RPSVersion.Status.PUBLISHED:
        raise ValidationError("Reschedule published plan membutuhkan alasan")
    offering = plan.rps.offering
    if (
        offering.starts_on
        and offering.ends_on
        and not offering.starts_on <= new_date <= offering.ends_on
    ):
        raise ValidationError("Tanggal pengganti di luar semester")
    plan.rescheduled_from = plan.planned_date
    plan.planned_date = new_date
    plan.reschedule_reason = reason
    plan.rescheduled_by = user
    plan.save(
        update_fields=[
            "rescheduled_from",
            "planned_date",
            "reschedule_reason",
            "rescheduled_by",
            "updated_at",
        ]
    )
    return plan


@transaction.atomic
def record_week_execution(plan: WeeklyPlan, *, user, actual: dict[str, Any]) -> WeeklyPlan:
    required = {"occurred_at", "minutes", "attendance_count", "materials", "evidence_ids"}
    if missing := required - set(actual):
        raise ValidationError(f"Catatan realisasi belum lengkap: {', '.join(sorted(missing))}")
    if int(actual["minutes"]) <= 0:
        raise ValidationError("Menit realisasi harus lebih dari nol")
    plan.actual = {**actual, "recorded_by": str(user.pk)}
    plan.execution_recorded_at = timezone.now()
    plan.save(update_fields=["actual", "execution_recorded_at", "updated_at"])
    return plan


def planned_vs_actual(rps: RPSVersion) -> list[dict[str, Any]]:
    rows = []
    for plan in rps.weekly_plans.order_by("week"):
        planned = plan.contact_minutes + plan.structured_minutes + plan.independent_minutes
        actual = int(plan.actual.get("minutes", 0)) if plan.actual else None
        rows.append(
            {
                "week": plan.week,
                "planned_minutes": planned,
                "actual_minutes": actual,
                "deviation_minutes": None if actual is None else actual - planned,
                "reason": plan.actual.get("deviation_reason", "") if plan.actual else "",
            }
        )
    return rows
