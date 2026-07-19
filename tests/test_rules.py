from decimal import Decimal

import pytest

from obe.shared.rules import grade_for, graduation_eligibility, max_credit_load, normalize_score


@pytest.mark.parametrize(
    ("raw", "maximum", "expected"),
    [(75, 100, Decimal("75.00")), (1, 3, Decimal("33.33")), (120, 120, Decimal("100.00"))],
)
def test_normalize_score(raw, maximum, expected):
    assert normalize_score(raw, maximum) == expected


@pytest.mark.parametrize("maximum", [0, -1])
def test_normalize_rejects_invalid_maximum(maximum):
    with pytest.raises(ValueError):
        normalize_score(1, maximum)


@pytest.mark.parametrize(
    ("score", "letter", "point"),
    [
        (85, "A", "4"),
        (80, "AB", "3.5"),
        (75, "B", "3"),
        (70, "BC", "2.5"),
        (60, "C", "2"),
        (40, "D", "1"),
        (0, "E", "0"),
    ],
)
def test_current_grade_boundaries(score, letter, point):
    assert grade_for(score) == (letter, Decimal(point))


def test_legacy_grade_boundary():
    assert grade_for(79.99, "LEGACY-ABCDE")[0] == "B"


@pytest.mark.parametrize(
    ("semester", "gpa", "returning", "reason"),
    [
        (1, None, False, "SEMESTER_1_MAX_20"),
        (2, 1.99, False, "SEMESTER_2_MAX_18"),
        (3, 3.0, False, "IPS_MAX_24"),
        (7, 4.0, True, "RETURNING_MAX_18"),
    ],
)
def test_credit_load(semester, gpa, returning, reason):
    assert (
        max_credit_load(semester=semester, last_gpa=gpa, returning=returning).reason_code == reason
    )


def test_credit_load_is_indeterminate_without_gpa():
    assert max_credit_load(semester=3, last_gpa=None, returning=False).outcome == "indeterminate"


def test_graduation_requires_every_condition():
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
    assert graduation_eligibility(valid).outcome == "pass"
    assert graduation_eligibility({**valid, "english_score": 399}).outcome == "fail"
