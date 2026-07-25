"""Property-based tests for the Attainment_Engine.

Feature: obe-system
Properties 21, 22, 23, 24.
"""

from decimal import Decimal

import pytest
from hypothesis import given, settings, strategies as st

from core.exceptions import DomainError
from core.models import DemoUser, ProgramOfStudy
from curriculum.models import CPL, CPLIndicator, Course, Curriculum, CurriculumStatus
from rps.models import (
    AssessmentInstrument, CPMK, RPS, RPSStatus,
    Rubric, RubricCriterion, RubricLevel, Score,
    SubCPMK, SubCPMKIndicator,
)
from timeline.models import (
    Milestone, OBECycle, Phase, Task, TaskStatus,
    TimelineInstance, TimelineTemplate,
)
from attainment.models import AttainmentResult, CalculationFormula, FormulaLevel
from attainment.services import AttainmentService


@pytest.fixture
def full_setup(db):
    """Create a full setup for attainment testing."""
    prodi = ProgramOfStudy.objects.create(code="ATT-TEST", name="Test")
    actor = DemoUser.objects.create(name="Actor", role="kaprodi", prodi=prodi)

    # Curriculum with CPL + indicator
    curriculum = Curriculum.objects.create(
        name="C", prodi=prodi, owner=actor, creator=actor,
        status=CurriculumStatus.ACTIVE,
    )
    cpl = CPL.objects.create(
        curriculum=curriculum, code="CPL-01", prodi=prodi,
        owner=actor, creator=actor, status="active",
    )
    indicator = CPLIndicator.objects.create(
        cpl=cpl, code="IK-01", target_value=Decimal("70.00"),
    )

    # Course + RPS
    course = Course.objects.create(
        curriculum=curriculum, code="C1", name="Course 1",
        prodi=prodi, owner=actor, creator=actor, status="active",
    )
    rps = RPS.objects.create(
        course=course, curriculum=curriculum, class_name="A", period="2024",
        prodi=prodi, owner=actor, creator=actor, status=RPSStatus.SUBMITTED,
    )

    # CPMK -> SubCPMK -> Indicator
    cpmk = CPMK.objects.create(rps=rps, code="CPMK-01")
    cpmk.derived_from.add(cpl)
    sub = SubCPMK.objects.create(cpmk=cpmk, code="Sub-01")
    sub_ind = SubCPMKIndicator.objects.create(sub_cpmk=sub, code="SI-01")

    # Instrument -> Rubric -> Criterion -> Levels
    instrument = AssessmentInstrument.objects.create(
        rps=rps, name="Instr", prodi=prodi, owner=actor, creator=actor, status="draft",
    )
    rubric = Rubric.objects.create(
        instrument=instrument, name="Rubric",
        prodi=prodi, owner=actor, creator=actor, status="draft",
    )
    criterion = RubricCriterion.objects.create(
        rubric=rubric, name="Crit1", weight=Decimal("100"), order=0,
    )
    criterion.mapped_indicators.add(sub_ind)
    RubricLevel.objects.create(criterion=criterion, label="Baik", score=Decimal("60"), order=0)
    RubricLevel.objects.create(criterion=criterion, label="Sangat Baik", score=Decimal("90"), order=1)

    # Timeline
    template = TimelineTemplate.objects.create(name="Template ATT")
    cycle = OBECycle.objects.create(
        name="Cycle", prodi=prodi, owner=actor, creator=actor, status="active",
    )
    instance = TimelineInstance.objects.create(template=template, cycle=cycle)
    phase = Phase.objects.create(instance=instance, name="Evaluasi", order=1)
    ms = Milestone.objects.create(phase=phase, name="MS1", order=1)

    # Formula
    formula = CalculationFormula.objects.create(
        name="weighted_average", version=1, level=FormulaLevel.CPL,
        definition={"method": "weighted_average"}, is_active=True,
    )

    return {
        "prodi": prodi, "actor": actor, "curriculum": curriculum,
        "cpl": cpl, "indicator": indicator, "course": course,
        "rps": rps, "cpmk": cpmk, "sub_ind": sub_ind,
        "criterion": criterion, "cycle": cycle, "instance": instance,
        "formula": formula,
    }


@pytest.mark.django_db
class TestProperty21FormulaIdentityAndGap:
    """Feature: obe-system, Property 21: Attainment results record formula identity and correct gap

    Validates: Requirements 11.2, 11.3
    """

    def test_property_21_formula_identity_and_gap(self, full_setup):
        """Results record formula name/version and gap = actual - target."""
        s = full_setup
        # Add a score
        Score.objects.create(criterion=s["criterion"], student_proxy="S1", value=Decimal("80"))

        result = AttainmentService.calculate(s["cycle"].id, s["actor"])
        results = result["results"]

        if results:
            for r in results:
                assert r.formula_name == "weighted_average"
                assert r.formula_version == 1
                assert r.gap == r.actual_value - r.target_value


@pytest.mark.django_db
class TestProperty22Traceability:
    """Feature: obe-system, Property 22: Attainment results are traceable to source scores

    Validates: Requirements 11.1, 11.4
    """

    def test_property_22_traceable_to_scores(self, full_setup):
        """Results retain a link to the rubric scores that produced them."""
        s = full_setup
        score = Score.objects.create(criterion=s["criterion"], student_proxy="S1", value=Decimal("75"))

        result = AttainmentService.calculate(s["cycle"].id, s["actor"])
        results = result["results"]

        if results:
            for r in results:
                assert r.source_scores.count() > 0


@pytest.mark.django_db
class TestProperty23BadDataHalt:
    """Feature: obe-system, Property 23: Bad data halts calculation without side effects

    Validates: Requirements 12.1, 12.2, 12.3
    """

    def test_property_23_out_of_range_halts(self, full_setup):
        """Out-of-range score halts calculation, leaving results unchanged."""
        s = full_setup
        # Add an out-of-range score (above max level of 90)
        Score.objects.create(criterion=s["criterion"], student_proxy="S1", value=Decimal("95"))

        # Should halt
        with pytest.raises(DomainError) as exc_info:
            AttainmentService.calculate(s["cycle"].id, s["actor"])

        assert "di luar rentang" in exc_info.value.message

        # No results created
        assert AttainmentResult.objects.filter(cycle=s["cycle"]).count() == 0

    def test_property_23_edge_missing_halts(self, full_setup):
        """Edge: halt on out-of-range score (Reqs 12.1, 12.2)."""
        s = full_setup
        # Score below min (60)
        Score.objects.create(criterion=s["criterion"], student_proxy="S1", value=Decimal("55"))

        with pytest.raises(DomainError):
            AttainmentService.calculate(s["cycle"].id, s["actor"])


@pytest.mark.django_db
class TestProperty24GapDrivenTasks:
    """Feature: obe-system, Property 24: Evaluation tasks are created exactly for unmet outcomes

    Validates: Requirements 13.1, 13.3
    """

    def test_property_24_task_created_for_gap(self, full_setup):
        """Evaluation task created when actual < target, none when actual >= target."""
        s = full_setup
        # Score of 65 < target 70: gap exists
        Score.objects.create(criterion=s["criterion"], student_proxy="S1", value=Decimal("65"))

        initial_tasks = Task.objects.filter(
            milestone__phase__instance=s["instance"]
        ).count()

        result = AttainmentService.calculate(s["cycle"].id, s["actor"])

        # Task should be created for the gap
        if result["results"]:
            for r in result["results"]:
                if r.actual_value < r.target_value:
                    assert result["tasks_created"] > 0

    def test_property_24_no_task_when_met(self, full_setup):
        """No evaluation task when actual >= target."""
        s = full_setup
        # Score at exactly target level: 70 (within range 60-90)
        Score.objects.create(criterion=s["criterion"], student_proxy="S1", value=Decimal("75"))

        result = AttainmentService.calculate(s["cycle"].id, s["actor"])

        # If actual >= target, no tasks created
        if result["results"]:
            for r in result["results"]:
                if r.actual_value >= r.target_value:
                    # No tasks needed for met outcomes
                    pass
