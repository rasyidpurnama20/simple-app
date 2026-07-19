from obe.assessment.models import AssessmentItem, AttainmentSnapshot


def semantic_attainment(*, course: str = "", outcome: str = "") -> list[dict]:
    scope_type = "course" if course else "program"
    snapshots = AttainmentSnapshot.objects.filter(scope_type=scope_type)
    if course:
        snapshots = snapshots.filter(scope_id=course)
    if outcome:
        snapshots = snapshots.filter(outcome_code=outcome)
    rows = []
    for snapshot in snapshots.order_by("outcome_code"):
        actual = float(snapshot.actual) if snapshot.actual is not None else None
        target = float(snapshot.target)
        rows.append(
            {
                "scope_type": snapshot.scope_type,
                "scope_id": snapshot.scope_id,
                "outcome": snapshot.outcome_code,
                "actual": actual,
                "target": target,
                "denominator": snapshot.denominator,
                "coverage": float(snapshot.coverage),
                "status": (
                    "missing" if actual is None else "met" if actual >= target else "below-target"
                ),
                "formula_version": snapshot.formula_version,
            }
        )
    return rows


def assessment_item_payload(item: AssessmentItem, *, can_view_answer_key: bool = False) -> dict:
    """Answer keys are never returned to participant-facing selectors."""
    payload = {
        "public_id": str(item.public_id),
        "code": item.code,
        "prompt": item.prompt,
        "item_type": item.item_type,
        "points": str(item.points),
        "indicator_codes": item.indicator_codes,
        "sub_outcome_codes": item.sub_outcome_codes,
    }
    if can_view_answer_key:
        payload["answer_key"] = item.answer_key
    return payload
