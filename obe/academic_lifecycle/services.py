from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from django.core.exceptions import ValidationError

from obe.academic_lifecycle.models import AcademicResult, StudentProfile
from obe.shared.rules import Decision, max_credit_load


def calculate_progress(student: StudentProfile) -> dict:
    rows = AcademicResult.objects.filter(student=student)
    best: dict[UUID, AcademicResult] = {}
    for row in rows.order_by("course_public_id", "-grade_point", "attempt"):
        best.setdefault(row.course_public_id, row)
    chosen = list(best.values())
    earned = sum(row.credits for row in chosen if row.passed)
    attempted = sum(row.credits for row in chosen if row.grade_point is not None)
    points = sum(
        Decimal(row.credits) * row.grade_point for row in chosen if row.grade_point is not None
    )
    gpa = (
        Decimal("0")
        if attempted == 0
        else (points / attempted).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    )
    return {
        "attempted_credits": attempted,
        "earned_credits": earned,
        "gpa": gpa,
        "remaining_credits": max(0, 144 - earned),
        "repeats": rows.count() - len(chosen),
    }


def validate_plan(
    *, student: StudentProfile, semester: int, requested_credits: int, last_gpa, returning=False
) -> Decision:
    decision = max_credit_load(semester=semester, last_gpa=last_gpa, returning=returning)
    if decision.outcome == "indeterminate":
        return decision
    maximum = int(decision.trace[-1].split("=")[-1])
    if requested_credits > maximum:
        raise ValidationError(
            {"credits": f"Maksimum {maximum} SKS", "reason_code": decision.reason_code}
        )
    return decision
