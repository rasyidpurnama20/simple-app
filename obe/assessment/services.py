from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from obe.assessment.models import Score, Submission
from obe.shared.rules import grade_for, normalize_score


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
    normalized = normalize_score(raw, maximum)
    letter, point = grade_for(normalized, scheme)
    return Score.objects.create(
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
