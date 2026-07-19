from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Iterable
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from obe.assessment.models import (
    AssessmentInstrument,
    CompetencyScale,
    CriterionScore,
    ExamEquivalenceReview,
    ParallelExamPolicy,
    QuestionSetVersion,
    Rubric,
    RubricCriterion,
    Score,
    ScoreRevision,
    Submission,
    SubmissionGroup,
)
from obe.shared.rules import grade_for, normalize_score
from obe.shared.services import ActorContext, record_change


def _actor(user) -> ActorContext:
    return ActorContext(str(user.pk), user.get_username(), "assessment")


def _checksum(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def competency_for(score: Decimal, scale: CompetencyScale | None) -> str:
    if scale is None:
        return ""
    scale.full_clean()
    value = Decimal(str(score))
    for band in scale.bands:
        if Decimal(str(band["min"])) <= value <= Decimal(str(band["max"])):
            return str(band["code"])
    raise ValidationError("Nilai tidak tercakup skala kompetensi")


@transaction.atomic
def create_question_set(
    *,
    instrument: AssessmentInstrument,
    parallel_group: str,
    code: str,
    questions: list[dict],
    coverage: dict,
    difficulty: dict,
    authored_by,
) -> QuestionSetVersion:
    if instrument.code not in {"MIDTERM", "FINAL", "UTS", "UAS"}:
        raise ValidationError("Question set paralel hanya untuk UTS/UAS")
    version = (
        QuestionSetVersion.objects.filter(instrument=instrument, code=code)
        .order_by("-version")
        .values_list("version", flat=True)
        .first()
        or 0
    ) + 1
    row = QuestionSetVersion(
        instrument=instrument,
        parallel_group=parallel_group,
        code=code,
        version=version,
        blueprint_checksum=_checksum({"coverage": coverage, "difficulty": difficulty}),
        question_checksum=_checksum(questions),
        coverage=coverage,
        difficulty=difficulty,
        authored_by=authored_by,
        created_by_actor_id=str(authored_by.pk),
        updated_by_actor_id=str(authored_by.pk),
    )
    row.full_clean()
    row.save()
    return row


@transaction.atomic
def review_parallel_exam(
    *,
    question_sets: Iterable[QuestionSetVersion],
    policy: ParallelExamPolicy,
    reviewer,
    equivalence_report: dict,
    difference_reason: str = "",
) -> ExamEquivalenceReview:
    rows = list(question_sets)
    if len(rows) < 2:
        raise ValidationError("Moderasi paralel memerlukan minimal dua kelas")
    if policy.status != "active":
        raise ValidationError("Kebijakan ujian paralel harus aktif")
    groups = {row.parallel_group for row in rows}
    exam_codes = {row.instrument.code for row in rows}
    if len(groups) != 1 or len(exam_codes) != 1 or not next(iter(groups)).strip():
        raise ValidationError("Question set harus berada pada group dan jenis ujian yang sama")
    same_questions = len({row.question_checksum for row in rows}) == 1
    if policy.strict_same_question and not same_questions:
        raise ValidationError("Kebijakan strict-same-question memblokir soal berbeda")
    same_blueprint = len({row.blueprint_checksum for row in rows}) == 1
    reported_equivalent = bool(
        equivalence_report.get("coverage_equivalent")
        and equivalence_report.get("difficulty_equivalent")
    )
    equivalent = same_blueprint or reported_equivalent
    if not equivalent:
        raise ValidationError("Kesetaraan coverage dan tingkat kesulitan belum terbukti")
    if not same_questions and not difference_reason.strip():
        raise ValidationError("Soal berbeda memerlukan alasan terdokumentasi")
    review = ExamEquivalenceReview.objects.create(
        parallel_group=next(iter(groups)),
        exam_code=next(iter(exam_codes)),
        policy=policy,
        equivalent=equivalent,
        equivalence_report={
            **equivalence_report,
            "same_blueprint": same_blueprint,
            "same_questions": same_questions,
            "question_sets": [str(row.public_id) for row in rows],
        },
        difference_reason=difference_reason,
        status="gpm_reviewed",
        reviewed_by=reviewer,
        reviewed_at=timezone.now(),
    )
    review.question_sets.set(rows)
    QuestionSetVersion.objects.filter(pk__in=[row.pk for row in rows]).update(
        status="gpm_review", updated_by_actor_id=str(reviewer.pk)
    )
    return review


@transaction.atomic
def approve_parallel_exam(review: ExamEquivalenceReview, *, user) -> ExamEquivalenceReview:
    locked = ExamEquivalenceReview.objects.select_for_update().get(pk=review.pk)
    if locked.status != "gpm_reviewed" or not locked.equivalent:
        raise ValidationError("Review kesetaraan belum siap disetujui")
    if locked.reviewed_by_id == user.pk:
        raise ValidationError("Reviewer GPM tidak boleh menjadi approver Prodi")
    locked.status = "approved"
    locked.approved_by = user
    locked.approved_at = timezone.now()
    locked.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
    QuestionSetVersion.objects.filter(equivalence_reviews=locked).update(
        status="approved", updated_by_actor_id=str(user.pk)
    )
    record_change(
        actor=_actor(user),
        action="assessment.parallel-exam.approve",
        object_type="exam-equivalence-review",
        object_id=str(locked.id),
        summary="Kesetaraan ujian paralel disetujui",
        after=locked.equivalence_report,
        reason=locked.difference_reason or "Blueprint dan question set ekuivalen",
    )
    return locked


@transaction.atomic
def release_question_set(
    question_set: QuestionSetVersion, *, review: ExamEquivalenceReview, user
) -> QuestionSetVersion:
    if review.status != "approved" or not review.question_sets.filter(pk=question_set.pk).exists():
        raise ValidationError("Question set belum memiliki approval kesetaraan")
    question_set.status = "released"
    question_set.updated_by_actor_id = str(user.pk)
    question_set.save(update_fields=["status", "updated_by_actor_id", "updated_at"])
    return question_set


@transaction.atomic
def analyze_parallel_results(
    review: ExamEquivalenceReview, *, class_scores: dict[str, list[Decimal]], user
) -> dict:
    if (
        review.status != "approved"
        or len(class_scores) < 2
        or any(not rows for rows in class_scores.values())
    ):
        raise ValidationError("Analisis hasil memerlukan review approved dan minimal dua kelas")
    means = {
        code: (sum((Decimal(str(value)) for value in values), Decimal("0")) / len(values)).quantize(
            Decimal("0.01")
        )
        for code, values in class_scores.items()
    }
    disparity = max(means.values()) - min(means.values())
    result = {
        "means": {key: str(value) for key, value in means.items()},
        "disparity": str(disparity),
        "threshold": str(review.policy.disparity_threshold),
        "flagged": disparity > review.policy.disparity_threshold,
    }
    review.result_analysis = result
    review.save(update_fields=["result_analysis", "updated_at"])
    record_change(
        actor=_actor(user),
        action="assessment.parallel-exam.analyze",
        object_type="exam-equivalence-review",
        object_id=str(review.id),
        summary="Disparity hasil kelas paralel dianalisis",
        after=result,
    )
    return result


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


def _submission_payload(submission: Submission) -> dict:
    return {
        "instrument": str(submission.instrument.public_id),
        "student_id": submission.student_id,
        "group": str(submission.group.public_id) if submission.group_id else "",
        "attempt": submission.attempt,
        "response": submission.response,
        "evidence_manifest_ids": sorted(submission.evidence_manifest_ids),
        "version": submission.version,
    }


@transaction.atomic
def save_submission_draft(
    *,
    instrument: AssessmentInstrument,
    student_id: str,
    attempt: int,
    response: dict,
    evidence_manifest_ids: list[str],
    group: SubmissionGroup | None = None,
    source_version: dict | None = None,
) -> Submission:
    if attempt < 1 or attempt > instrument.attempts:
        raise ValidationError("Attempt submission di luar batas instrumen")
    if group and (group.instrument_id != instrument.pk or student_id not in group.member_ids):
        raise ValidationError("Anggota atau instrumen grup submission tidak sesuai")
    if len(evidence_manifest_ids) != len(set(evidence_manifest_ids)):
        raise ValidationError("Evidence submission tidak boleh duplikat")
    submission, _ = Submission.objects.get_or_create(
        instrument=instrument,
        student_id=student_id,
        attempt=attempt,
        defaults={"group": group},
    )
    if submission.status == "final":
        raise ValidationError("Submission final immutable; lakukan reopening resmi")
    submission.group = group
    submission.response = response
    submission.evidence_manifest_ids = evidence_manifest_ids
    submission.status = "draft" if submission.status != "reopened" else "reopened"
    submission.source_version = source_version or submission.source_version
    submission.save()
    return submission


@transaction.atomic
def finalize_submission(
    submission: Submission, *, user, now=None, allow_late: bool = False
) -> Submission:
    current = now or timezone.now()
    if submission.status not in {"draft", "reopened"}:
        raise ValidationError("Hanya submission draft/reopened yang dapat difinalkan")
    if submission.group_id and submission.student_id not in submission.group.member_ids:
        raise ValidationError("Mahasiswa bukan anggota grup submission")
    deadline = submission.instrument.deadline_at
    late = bool(deadline and current > deadline)
    if late and not allow_late:
        raise ValidationError("Deadline submission telah lewat")
    if not submission.response and not submission.evidence_manifest_ids:
        raise ValidationError("Submission final memerlukan response atau evidence")
    submission.submitted_at = current
    submission.late = late
    submission.receipt_checksum = _checksum(_submission_payload(submission))
    submission.status = "final"
    submission.updated_by_actor_id = str(user.pk)
    submission.save()
    record_change(
        actor=_actor(user),
        action="assessment.submission.finalize",
        object_type="submission",
        object_id=str(submission.public_id),
        summary="Submission difinalkan",
        after={"receipt_checksum": submission.receipt_checksum, "late": late},
    )
    return submission


@transaction.atomic
def reopen_submission(submission: Submission, *, user, reason: str) -> Submission:
    if submission.status != "final" or not reason.strip():
        raise ValidationError("Reopening hanya untuk submission final dan wajib beralasan")
    now = timezone.now()
    Submission.objects.filter(pk=submission.pk, status="final").update(
        status="reopened",
        reopened_reason=reason,
        reopened_by=user,
        reopened_at=now,
        updated_by_actor_id=str(user.pk),
    )
    submission.refresh_from_db()
    record_change(
        actor=_actor(user),
        action="assessment.submission.reopen",
        object_type="submission",
        object_id=str(submission.public_id),
        summary="Submission final dibuka kembali",
        reason=reason,
    )
    return submission


@transaction.atomic
def grade_submission(
    *,
    submission: Submission,
    raw: Decimal,
    maximum: Decimal,
    assessor,
    rubric_trace: dict,
    scheme: str,
    competency_scale: CompetencyScale | None = None,
    source_version: dict | None = None,
) -> Score:
    if submission.instrument.status == "published" and not submission.instrument.published_at:
        raise ValidationError("Snapshot publikasi instrumen tidak valid")
    calculated = normalize_score(raw, maximum)
    normalized = min(calculated, Decimal("100"))
    letter, point = grade_for(normalized, scheme)
    score = Score.objects.create(
        submission=submission,
        raw_score=raw,
        max_score=maximum,
        normalized=normalized,
        attempt=submission.attempt,
        letter=letter,
        grade_point=point,
        rubric_trace=rubric_trace,
        assessor=assessor,
        published_at=timezone.now(),
        rule_package=scheme,
        rule_package_version=1,
        competency_category=competency_for(normalized, competency_scale),
        source_version=source_version or {},
        calculation_trace=[
            f"normalized=round_half_up({raw}/{maximum}*100)={calculated}",
            f"capped={normalized}",
            f"grade={letter}",
        ],
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
def record_historical_score(
    *,
    submission: Submission,
    raw: Decimal,
    maximum: Decimal,
    normalized: Decimal,
    letter: str,
    grade_point: Decimal,
    assessor,
    scheme: str,
    scheme_version: int,
    source_version: dict,
    competency_scale: CompetencyScale | None = None,
) -> Score:
    """Persist an official historical grade without converting it to the current scheme."""
    score = Score(
        submission=submission,
        raw_score=raw,
        max_score=maximum,
        normalized=normalized,
        attempt=submission.attempt,
        letter=letter,
        grade_point=grade_point,
        rubric_trace={"source": "historical-import"},
        feedback={"items": []},
        assessor=assessor,
        published_at=timezone.now(),
        rule_package=scheme,
        rule_package_version=scheme_version,
        competency_category=competency_for(normalized, competency_scale),
        source_version=source_version,
        calculation_trace=["historical-grade-preserved", f"source_letter={letter}"],
    )
    score.full_clean()
    score.save()
    return score


def best_attempt(scores: Iterable[Score]) -> Score | None:
    eligible = [row for row in scores if row.state in {"graded", "regraded"}]
    return max(
        eligible,
        key=lambda row: (
            row.grade_point if row.grade_point is not None else Decimal("-1"),
            row.normalized,
            row.attempt,
        ),
        default=None,
    )


def requirement_met(score: Score, *, thesis: bool = False) -> bool:
    rank = {"E": 0, "D": 1, "C": 2, "BC": 3, "B": 4, "AB": 5, "A": 6}
    minimum = "B" if thesis else "C"
    return score.state in {"graded", "regraded"} and rank.get(score.letter, -1) >= rank[minimum]


@transaction.atomic
def set_score_feedback(score: Score, *, user, feedback: list[dict]) -> Score:
    if not feedback:
        raise ValidationError("Feedback asesmen wajib tersedia")
    for row in feedback:
        if not row.get("criterion_code") and not row.get("outcome_code"):
            raise ValidationError("Feedback harus menunjuk kriteria atau outcome")
        if not row.get("text") and not row.get("file_manifest_id"):
            raise ValidationError("Feedback harus memuat teks atau file")
    score.feedback = {"items": feedback, "updated_by": str(user.pk)}
    score.save(update_fields=["feedback", "updated_at"])
    return score


@transaction.atomic
def request_score_revision(
    score: Score, *, user, raw: Decimal, maximum: Decimal, reason: str
) -> ScoreRevision:
    if not score.published_at:
        raise ValidationError("Maker-checker hanya berlaku untuk nilai yang sudah dipublikasikan")
    revision = ScoreRevision(
        score=score,
        proposed_raw_score=raw,
        proposed_max_score=maximum,
        reason=reason,
        requested_by=user,
        notification_key=f"score-revision:{score.public_id}:{uuid.uuid4()}",
    )
    revision.full_clean()
    revision.save()
    return revision


@transaction.atomic
def approve_score_revision(
    revision: ScoreRevision, *, user, competency_scale: CompetencyScale | None = None
) -> Score:
    locked = (
        ScoreRevision.objects.select_for_update()
        .select_related("score__submission")
        .get(pk=revision.pk)
    )
    if locked.status != "pending":
        raise ValidationError("Revisi nilai bukan pending")
    if locked.requested_by_id == user.pk:
        raise ValidationError("Pemohon tidak boleh menyetujui revisi nilai sendiri")
    previous = locked.score
    calculated = normalize_score(locked.proposed_raw_score, locked.proposed_max_score)
    normalized = min(calculated, Decimal("100"))
    letter, point = grade_for(normalized, previous.rule_package)
    replacement = Score.objects.create(
        submission=previous.submission,
        raw_score=locked.proposed_raw_score,
        max_score=locked.proposed_max_score,
        normalized=normalized,
        attempt=previous.attempt,
        letter=letter,
        grade_point=point,
        state="regraded",
        rubric_trace={**previous.rubric_trace, "supersedes_score": str(previous.public_id)},
        feedback=previous.feedback,
        assessor=previous.assessor,
        published_at=timezone.now(),
        change_reason=locked.reason,
        rule_package=previous.rule_package,
        rule_package_version=previous.rule_package_version,
        competency_category=competency_for(normalized, competency_scale),
        source_version=previous.source_version,
        calculation_trace=[
            f"normalized=round_half_up({locked.proposed_raw_score}/{locked.proposed_max_score}*100)={calculated}",
            f"capped={normalized}",
            f"grade={letter}",
            f"supersedes={previous.public_id}",
        ],
    )
    locked.status = "approved"
    locked.approved_by = user
    locked.decided_at = timezone.now()
    locked.recalculation = {
        "previous_score": str(previous.public_id),
        "replacement_score": str(replacement.public_id),
        "normalized": str(normalized),
        "letter": letter,
    }
    locked.full_clean()
    locked.save(
        update_fields=[
            "status",
            "approved_by",
            "decided_at",
            "recalculation",
            "updated_at",
        ]
    )
    record_change(
        actor=_actor(user),
        action="assessment.grade.revision.approve",
        object_type="score",
        object_id=str(replacement.public_id),
        summary="Perubahan nilai published disetujui dan dihitung ulang",
        before={"normalized": str(previous.normalized), "letter": previous.letter},
        after={"normalized": str(normalized), "letter": letter},
        reason=locked.reason,
    )
    return replacement


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
