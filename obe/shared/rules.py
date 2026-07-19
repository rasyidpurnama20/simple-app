from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any


@dataclass(frozen=True)
class Decision:
    outcome: str
    reason_code: str
    inputs: dict[str, Any]
    trace: tuple[str, ...]


LEGACY = ((80, "A", 4), (70, "B", 3), (60, "C", 2), (51, "D", 1), (0, "E", 0))
CURRENT = (
    (85, "A", 4),
    (80, "AB", 3.5),
    (75, "B", 3),
    (70, "BC", 2.5),
    (60, "C", 2),
    (40, "D", 1),
    (0, "E", 0),
)

RULE_PACKAGE_POLICIES: dict[str, dict[str, Any]] = {
    "LEGACY-ABCDE": {
        "cohort_from": 2020,
        "cohort_to": 2023,
        "grade_scheme": LEGACY,
        "minimum_passing_grade": "C",
        "minimum_thesis_grade": "B",
        "progress_milestones": (
            ("end", 3, None, None),
            ("end", 7, None, None),
            ("end", 14, None, None),
        ),
    },
    "CURRENT-AABBC": {
        "cohort_from": 2024,
        "cohort_to": None,
        "grade_scheme": CURRENT,
        "minimum_passing_grade": "C",
        "minimum_thesis_grade": "B",
        "progress_milestones": (
            ("start", 3, 25, Decimal("2.50")),
            ("start", 5, 50, Decimal("2.50")),
            ("start", 13, 108, Decimal("2.50")),
        ),
    },
}


def package_for_cohort(cohort: int) -> str:
    matches = [
        code
        for code, policy in RULE_PACKAGE_POLICIES.items()
        if cohort >= policy["cohort_from"]
        and (policy["cohort_to"] is None or cohort <= policy["cohort_to"])
    ]
    if len(matches) != 1:
        raise ValueError(f"Cohort {cohort} tidak memiliki tepat satu paket aturan")
    return matches[0]


def normalize_score(raw: Decimal | float, maximum: Decimal | float) -> Decimal:
    raw_d, max_d = Decimal(str(raw)), Decimal(str(maximum))
    if max_d <= 0:
        raise ValueError("maximum harus lebih dari nol")
    if raw_d < 0:
        raise ValueError("raw score tidak boleh negatif")
    return ((raw_d / max_d) * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def grade_for(score: Decimal | float, scheme: str = "CURRENT-AABBC") -> tuple[str, Decimal]:
    value = Decimal(str(score))
    if not 0 <= value <= 100:
        raise ValueError("nilai harus 0–100")
    if scheme not in RULE_PACKAGE_POLICIES:
        raise ValueError("paket skala nilai tidak dikenal")
    thresholds = RULE_PACKAGE_POLICIES[scheme]["grade_scheme"]
    for minimum, letter, point in thresholds:
        if value >= Decimal(str(minimum)):
            return letter, Decimal(str(point))
    raise AssertionError("threshold tidak lengkap")


def max_credit_load(
    *,
    semester: int,
    last_gpa: Decimal | float | None,
    returning: bool,
    package: str = "CURRENT-AABBC",
) -> Decision:
    if package not in RULE_PACKAGE_POLICIES:
        raise ValueError("paket aturan tidak dikenal")
    inputs = {
        "semester": semester,
        "last_gpa": last_gpa,
        "returning": returning,
        "package": package,
    }
    if returning:
        return Decision("pass", "RETURNING_MAX_18", inputs, ("returning=true", "max=18"))
    if semester == 1:
        return Decision("pass", "SEMESTER_1_MAX_20", inputs, ("semester=1", "max=20"))
    if semester == 2:
        maximum = 18 if last_gpa is not None and Decimal(str(last_gpa)) < 2 else 20
        return Decision(
            "pass", f"SEMESTER_2_MAX_{maximum}", inputs, (f"IPS={last_gpa}", f"max={maximum}")
        )
    if last_gpa is None:
        return Decision("indeterminate", "IPS_MISSING", inputs, ("IPS tidak tersedia",))
    gpa = Decimal(str(last_gpa))
    maximum = 18 if gpa < 2 else 20 if gpa < Decimal("2.5") else 22 if gpa < 3 else 24
    return Decision("pass", f"IPS_MAX_{maximum}", inputs, (f"IPS={gpa}", f"max={maximum}"))


def progress_evaluation(
    *,
    package: str,
    semester: int,
    timing: str,
    earned_credits: int,
    gpa: Decimal | float | None,
) -> Decision:
    if package not in RULE_PACKAGE_POLICIES:
        raise ValueError("paket aturan tidak dikenal")
    inputs = {
        "package": package,
        "semester": semester,
        "timing": timing,
        "earned_credits": earned_credits,
        "gpa": gpa,
    }
    milestones = RULE_PACKAGE_POLICIES[package]["progress_milestones"]
    match = next((item for item in milestones if item[0:2] == (timing, semester)), None)
    if match is None:
        return Decision("indeterminate", "MILESTONE_NOT_APPLICABLE", inputs, ("no milestone",))
    _, _, minimum_credits, minimum_gpa = match
    if minimum_credits is None or minimum_gpa is None:
        return Decision(
            "pass",
            "LEGACY_MILESTONE_RECORDED",
            inputs,
            (f"{timing}-semester={semester}", "historical rule package"),
        )
    if gpa is None:
        return Decision("indeterminate", "MILESTONE_GPA_MISSING", inputs, ("gpa=missing",))
    passed = earned_credits >= minimum_credits and Decimal(str(gpa)) >= minimum_gpa
    return Decision(
        "pass" if passed else "fail",
        "MILESTONE_PASS" if passed else "MILESTONE_FAIL",
        inputs,
        (
            f"earned_credits={earned_credits}>={minimum_credits}",
            f"gpa={gpa}>={minimum_gpa}",
        ),
    )


def graduation_eligibility(data: dict[str, Any], package: str = "CURRENT-AABBC") -> Decision:
    if package not in RULE_PACKAGE_POLICIES:
        raise ValueError("paket aturan tidak dikenal")
    checks = {
        "total_credits": data.get("total_credits", 0) >= 144,
        "required_credits": data.get("required_credits", 0) >= 126,
        "elective_credits": data.get("elective_credits", 0) >= 18,
        "pkl": bool(data.get("pkl")),
        "kkn": bool(data.get("kkn")),
        "thesis_credits": data.get("thesis_credits", 0) >= 6,
        "thesis_grade": data.get("thesis_grade") in {"A", "AB", "B"},
        "english": data.get("english_score", 0) >= 400,
        "active": data.get("status") == "active",
        "repository": bool(data.get("repository_complete")),
    }
    failed = [name for name, passed in checks.items() if not passed]
    outcome = "pass" if not failed else "fail"
    code = "GRADUATION_ELIGIBLE" if not failed else "GRADUATION_REQUIREMENTS_MISSING"
    trace = (f"package={package}",) + tuple(
        f"{key}={'pass' if value else 'fail'}" for key, value in checks.items()
    )
    return Decision(outcome, code, {**data, "package": package, "failed": failed}, trace)
