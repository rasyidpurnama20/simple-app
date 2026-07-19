from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from obe.assessment.models import (
    AssessmentInstrument,
    CriterionScore,
    Rubric,
    RubricCriterion,
    Score,
    Submission,
)
from obe.shared.rules import grade_for, normalize_score
from obe.shared.services import ActorContext, record_change


def _actor(user) -> ActorContext:
    return ActorContext(str(user.pk), user.get_username(), "assessment")


def rubric_report(rubric: Rubric) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    criteria = list(rubric.criteria.order_by("order", "code"))
    if not criteria:
        errors.append({"code": "RUBRIC_CRITERION_MISSING", "detail": rubric.code})
    total = sum((row.weight for row in criteria), Decimal("0"))
    if total != Decimal("100"):
        errors.append({"code": "RUBRIC_WEIGHT_NOT_100", "detail": str(total)})
    for row in criteria:
        if not row.indicator_codes or not row.sub_outcome_codes:
            errors.append({"code": "RUBRIC_MAPPING_MISSING", "detail": row.code})
    levels = list(rubric.levels.order_by("minimum", "maximum"))
    if rubric.kind not in {"numeric", "checklist", "pass_fail"} and not levels:
        errors.append({"code": "RUBRIC_LEVEL_MISSING", "detail": rubric.code})
    for previous, current in zip(levels, levels[1:], strict=False):
        if current.minimum <= previous.maximum:
            errors.append(
                {"code": "RUBRIC_LEVEL_OVERLAP", "detail": f"{previous.code}/{current.code}"}
            )
    return {"valid": not errors, "errors": errors, "weight": total}


@transaction.atomic
def publish_rubric(rubric: Rubric, *, user) -> Rubric:
    report = rubric_report(rubric)
    if not report["valid"]:
        raise ValidationError({"rubric": report["errors"]})
    if rubric.status != "draft":
        raise ValidationError("Hanya rubrik draft yang dapat dipublikasikan")
    rubric.status = "published"
    rubric.updated_by_actor_id = str(user.pk)
    rubric.save(update_fields=["status", "updated_by_actor_id", "updated_at"])
    return rubric


def assessment_plan_report(
    instruments: Iterable[AssessmentInstrument], *, teaching_starts_at=None
) -> dict[str, Any]:
    rows = list(instruments)
    errors: list[dict[str, str]] = []
    total = sum((row.weight for row in rows), Decimal("0"))
    if total != Decimal("100"):
        errors.append({"code": "ASSESSMENT_WEIGHT_NOT_100", "detail": str(total)})
    codes: set[str] = set()
    for row in rows:
        if row.code in codes:
            errors.append({"code": "ASSESSMENT_CODE_DUPLICATE", "detail": row.code})
        codes.add(row.code)
        if not row.mappings:
            errors.append({"code": "ASSESSMENT_MAPPING_MISSING", "detail": row.code})
        blueprint_fields = {
            "outcome_distribution",
            "difficulty",
            "form",
            "durationMinutes",
            "coverage",
        }
        if not row.blueprint or blueprint_fields - set(row.blueprint):
            errors.append({"code": "ASSESSMENT_BLUEPRINT_MISSING", "detail": row.code})
        if not row.evidence_required:
            errors.append({"code": "ASSESSMENT_EVIDENCE_NOT_REQUIRED", "detail": row.code})
        allocation = sum(
            (Decimal(str(item.get("allocation_weight", 0))) for item in row.mappings),
            Decimal("0"),
        )
        if allocation != Decimal("100"):
            errors.append({"code": "ASSESSMENT_MAPPING_WEIGHT_NOT_100", "detail": row.code})
        if any(
            not item.get("indicator_codes") or not item.get("sub_outcome_codes")
            for item in row.mappings
        ):
            errors.append({"code": "ASSESSMENT_MAPPING_BROKEN", "detail": row.code})
        if teaching_starts_at and row.schedule < teaching_starts_at:
            errors.append({"code": "ASSESSMENT_SCHEDULE_BEFORE_TEACHING", "detail": row.code})
    return {"valid": not errors, "errors": errors, "weight": total, "count": len(rows)}


@transaction.atomic
def publish_assessment_plan(
    instruments: Iterable[AssessmentInstrument], *, user, teaching_starts_at
) -> list[AssessmentInstrument]:
    rows = list(instruments)
    report = assessment_plan_report(rows, teaching_starts_at=teaching_starts_at)
    if timezone.now() >= teaching_starts_at:
        report["errors"].append(
            {"code": "ASSESSMENT_PUBLISH_AFTER_TEACHING", "detail": str(teaching_starts_at)}
        )
        report["valid"] = False
    if not report["valid"]:
        raise ValidationError({"assessment_plan": report["errors"]})
    now = timezone.now()
    for row in rows:
        if row.status != "draft" or row.published_at:
            raise ValidationError(f"Instrumen {row.code} bukan draft")
        if row.rubric_public_id:
            rubric = Rubric.objects.filter(public_id=row.rubric_public_id).first()
            if not rubric or rubric.status != "published" or not rubric_report(rubric)["valid"]:
                raise ValidationError(f"Rubrik instrumen {row.code} belum valid/published")
        row.status = "published"
        row.published_at = now
        row.updated_by_actor_id = str(user.pk)
        row.full_clean()
        row.save(update_fields=["status", "published_at", "updated_by_actor_id", "updated_at"])
    record_change(
        actor=_actor(user),
        action="approval.assessment-plan",
        object_type="assessment-plan",
        object_id=str(rows[0].rps_public_id or rows[0].offering_public_id),
        summary=f"Rencana asesmen dipublikasikan: {len(rows)} instrumen",
        after={"codes": [row.code for row in rows], "weight": str(report["weight"])},
        reason="Blueprint, pemetaan, jadwal, dan bobot valid",
    )
    return rows


def assessment_plan_snapshot(
    instruments: Iterable[AssessmentInstrument], *, teaching_starts_at=None
) -> list[dict[str, Any]]:
    return [
        {
            "public_id": str(row.public_id),
            "version": row.version,
            "code": row.code,
            "kind": row.kind,
            "weight": str(row.weight),
            "mappings": row.mappings,
            "rubric_public_id": str(row.rubric_public_id or ""),
            "blueprint": row.blueprint,
            "status": row.status,
            "published_before_teaching": bool(
                row.published_at
                and (teaching_starts_at is None or row.published_at < teaching_starts_at)
            ),
        }
        for row in sorted(instruments, key=lambda item: item.code)
    ]


@transaction.atomic
def grade_submission(
    *,
    submission: Submission,
    raw: Decimal,
    maximum: Decimal,
    assessor,
    rubric_trace: dict,
    scheme: str,
) -> Score:
    if submission.instrument.status == "published" and not submission.instrument.published_at:
        raise ValidationError("Snapshot publikasi instrumen tidak valid")
    normalized = normalize_score(raw, maximum)
    letter, point = grade_for(normalized, scheme)
    score = Score.objects.create(
        submission=submission,
        raw_score=raw,
        max_score=maximum,
        normalized=normalized,
        letter=letter,
        grade_point=point,
        rubric_trace=rubric_trace,
        assessor=assessor,
        published_at=timezone.now(),
    )
    AssessmentInstrument.objects.filter(
        pk=submission.instrument_id, first_score_at__isnull=True
    ).update(first_score_at=timezone.now())
    rubric_id = rubric_trace.get("rubric_public_id")
    if rubric_id:
        Rubric.objects.filter(public_id=rubric_id, used_at__isnull=True).update(
            used_at=timezone.now()
        )
    return score


@transaction.atomic
def grade_with_rubric(
    *,
    submission: Submission,
    rubric: Rubric,
    criterion_points: dict[str, Decimal],
    assessor,
    scheme: str,
    second_assessor=None,
    blind_reference: str = "",
) -> Score:
    report = rubric_report(rubric)
    if rubric.status != "published" or not report["valid"]:
        raise ValidationError("Rubrik harus valid dan published")
    criteria = list(rubric.criteria.order_by("order"))
    if set(criterion_points) != {row.code for row in criteria}:
        raise ValidationError("Nilai wajib tersedia tepat satu untuk setiap kriteria")
    traces = []
    total = Decimal("0")
    for criterion in criteria:
        points = Decimal(str(criterion_points[criterion.code]))
        if not Decimal("0") <= points <= Decimal("100"):
            raise ValidationError("Nilai kriteria harus 0–100")
        weighted = (points * criterion.weight / Decimal("100")).quantize(Decimal("0.001"))
        total += weighted
        traces.append(
            {"criterion": criterion.code, "points": str(points), "weighted": str(weighted)}
        )
    score = grade_submission(
        submission=submission,
        raw=total,
        maximum=Decimal("100"),
        assessor=assessor,
        rubric_trace={
            "rubric_public_id": str(rubric.public_id),
            "rubric_version": rubric.version,
            "instrument_public_id": str(submission.instrument.public_id),
            "criteria": traces,
            "response_version": submission.version,
        },
        scheme=scheme,
    )
    score.second_assessor = second_assessor
    score.blind_reference = blind_reference
    if second_assessor:
        score.moderation_state = "pending"
    score.save(
        update_fields=["second_assessor", "blind_reference", "moderation_state", "updated_at"]
    )
    CriterionScore.objects.bulk_create(
        [
            CriterionScore(
                score=score,
                criterion=criterion,
                points=Decimal(str(criterion_points[criterion.code])),
                weighted_score=Decimal(trace["weighted"]),
            )
            for criterion, trace in zip(criteria, traces, strict=True)
        ]
    )
    return score


@transaction.atomic
def moderate_score(
    score: Score, *, user, comment: str, reconciled_normalized: Decimal | None = None
) -> Score:
    if not score.second_assessor_id or user.pk != score.second_assessor_id or not comment.strip():
        raise ValidationError("Moderasi membutuhkan second marker dan komentar")
    score.moderation_state = "reconciled"
    score.moderation_comment = comment
    score.reconciliation = {
        "original": str(score.normalized),
        "reconciled": str(
            reconciled_normalized if reconciled_normalized is not None else score.normalized
        ),
        "actor": str(user.pk),
    }
    score.save(
        update_fields=["moderation_state", "moderation_comment", "reconciliation", "updated_at"]
    )
    return score


@transaction.atomic
def clone_rubric(source: Rubric, *, user) -> Rubric:
    version = Rubric.objects.filter(code=source.code).order_by("-version").first().version + 1
    clone = Rubric.objects.create(
        code=source.code,
        title=source.title,
        kind=source.kind,
        version=version,
        created_by_actor_id=str(user.pk),
        updated_by_actor_id=str(user.pk),
    )
    for row in source.criteria.order_by("order"):
        RubricCriterion.objects.create(
            rubric=clone,
            code=row.code,
            title=row.title,
            description=row.description,
            weight=row.weight,
            indicator_codes=row.indicator_codes,
            sub_outcome_codes=row.sub_outcome_codes,
            order=row.order,
        )
    for row in source.levels.order_by("order"):
        clone.levels.create(
            code=row.code,
            descriptor=row.descriptor,
            minimum=row.minimum,
            maximum=row.maximum,
            points=row.points,
            order=row.order,
        )
    return clone


@transaction.atomic
def regrade_submission(
    *,
    previous: Score,
    new_rubric: Rubric,
    criterion_points: dict[str, Decimal],
    assessor,
    scheme: str,
    reason: str,
) -> Score:
    if not reason.strip():
        raise ValidationError("Regrade wajib memiliki alasan")
    old_rubric_id = previous.rubric_trace.get("rubric_public_id")
    if old_rubric_id == str(new_rubric.public_id):
        raise ValidationError("Regrade harus menggunakan versi rubrik baru")
    score = grade_with_rubric(
        submission=previous.submission,
        rubric=new_rubric,
        criterion_points=criterion_points,
        assessor=assessor,
        scheme=scheme,
    )
    score.state = "regraded"
    score.change_reason = reason
    score.rubric_trace = {**score.rubric_trace, "supersedes_score": str(previous.public_id)}
    score.save(update_fields=["state", "change_reason", "rubric_trace", "updated_at"])
    record_change(
        actor=_actor(assessor),
        action="assessment.grade.regrade",
        object_type="score",
        object_id=str(score.public_id),
        summary="Nilai dihitung ulang dengan rubrik versi baru",
        before={"score": str(previous.normalized), "rubric": old_rubric_id},
        after={"score": str(score.normalized), "rubric": str(new_rubric.public_id)},
        reason=reason,
    )
    return score
