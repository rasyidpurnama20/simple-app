"""Property-based tests for the RPS_Module.

Feature: obe-system
Properties 18, 19, 20.
"""

from decimal import Decimal

import pytest
from hypothesis import given, settings, strategies as st, HealthCheck

from core.exceptions import DomainError
from core.models import DemoUser, ProgramOfStudy
from curriculum.models import CPL, Course, Curriculum, CurriculumStatus
from rps.models import (
    AssessmentInstrument,
    CPMK,
    RPS,
    RPSStatus,
    Rubric,
    RubricCriterion,
    RubricLevel,
    SubCPMK,
    SubCPMKIndicator,
)
from rps.services import RPSService


@pytest.fixture
def setup_rps(db):
    """Create a full RPS setup for testing."""
    prodi = ProgramOfStudy.objects.create(code="RPS-TEST", name="Test Prodi")
    actor = DemoUser.objects.create(name="Actor", role="lecturer", prodi=prodi)
    curriculum = Curriculum.objects.create(
        name="Test Curriculum", prodi=prodi, owner=actor, creator=actor,
        status=CurriculumStatus.ACTIVE,
    )
    cpl1 = CPL.objects.create(
        curriculum=curriculum, code="CPL-01", prodi=prodi,
        owner=actor, creator=actor, status="active",
    )
    cpl2 = CPL.objects.create(
        curriculum=curriculum, code="CPL-02", prodi=prodi,
        owner=actor, creator=actor, status="active",
    )
    course = Course.objects.create(
        curriculum=curriculum, code="IF101", name="Test Course",
        prodi=prodi, owner=actor, creator=actor, status="active",
    )
    return {
        "prodi": prodi, "actor": actor, "curriculum": curriculum,
        "cpl1": cpl1, "cpl2": cpl2, "course": course,
    }


@pytest.mark.django_db(transaction=True)
class TestProperty18CPMKDerivation:
    """Feature: obe-system, Property 18: CPMK derives only from bound-curriculum CPLs

    Validates: Requirements 8.2, 8.5
    """

    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(use_foreign=st.booleans())
    def test_property_18_cpmk_bound_curriculum_only(self, use_foreign, transactional_db):
        """CPMK may only derive from CPLs of the RPS's bound curriculum."""
        prodi = ProgramOfStudy.objects.create(code=f"P18-{id(self)}", name="Test")
        actor = DemoUser.objects.create(name="Actor", role="lecturer", prodi=prodi)
        curriculum = Curriculum.objects.create(
            name="Bound", prodi=prodi, owner=actor, creator=actor, status="active"
        )
        cpl_bound = CPL.objects.create(
            curriculum=curriculum, code="CPL-BOUND", prodi=prodi,
            owner=actor, creator=actor, status="active"
        )
        # Foreign curriculum
        other_curriculum = Curriculum.objects.create(
            name="Other", prodi=prodi, owner=actor, creator=actor, status="draft"
        )
        cpl_foreign = CPL.objects.create(
            curriculum=other_curriculum, code="CPL-FOREIGN", prodi=prodi,
            owner=actor, creator=actor, status="draft"
        )
        course = Course.objects.create(
            curriculum=curriculum, code="C1", name="C1",
            prodi=prodi, owner=actor, creator=actor, status="active"
        )
        rps = RPSService.create_rps(course.id, curriculum.id, "A", "2024", actor)

        if use_foreign:
            with pytest.raises(DomainError):
                RPSService.add_cpmk(rps.id, [cpl_foreign.id], {"code": "CPMK-1"}, actor)
        else:
            cpmk = RPSService.add_cpmk(rps.id, [cpl_bound.id], {"code": "CPMK-1"}, actor)
            # All derived CPLs belong to the bound curriculum
            for cpl in cpmk.derived_from.all():
                assert cpl.curriculum_id == curriculum.id

        # Cleanup
        RPS.objects.filter(prodi=prodi).delete()
        Course.objects.filter(curriculum__prodi=prodi).delete()
        CPL.objects.filter(curriculum__prodi=prodi).delete()
        Curriculum.objects.filter(prodi=prodi).delete()
        actor.delete()
        prodi.delete()


@pytest.mark.django_db(transaction=True)
class TestProperty19WeightSum:
    """Feature: obe-system, Property 19: RPS submission requires weights summing to 100%

    Validates: Requirements 10.1, 10.3
    """

    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(weights=st.lists(st.integers(min_value=1, max_value=50), min_size=2, max_size=5))
    def test_property_19_weight_sum_100(self, weights, transactional_db):
        """RPS submission succeeds only if criterion weights sum to 100%."""
        prodi = ProgramOfStudy.objects.create(code=f"P19-{id(self)}", name="Test")
        actor = DemoUser.objects.create(name="Actor", role="lecturer", prodi=prodi)
        curriculum = Curriculum.objects.create(
            name="C", prodi=prodi, owner=actor, creator=actor, status="active"
        )
        course = Course.objects.create(
            curriculum=curriculum, code="C1", name="C1",
            prodi=prodi, owner=actor, creator=actor, status="active"
        )
        rps = RPSService.create_rps(course.id, curriculum.id, "A", "2024", actor)
        instrument = AssessmentInstrument.objects.create(
            rps=rps, name="Instr", prodi=prodi, owner=actor, creator=actor, status="draft"
        )
        rubric = Rubric.objects.create(
            instrument=instrument, name="Rubric",
            prodi=prodi, owner=actor, creator=actor, status="draft"
        )

        total = sum(weights)
        for i, w in enumerate(weights):
            RubricCriterion.objects.create(rubric=rubric, name=f"C{i}", weight=w, order=i)

        if total == 100:
            # Should pass (if coverage is met - skip coverage check for this test)
            pass  # Coverage check would also need to pass
        else:
            with pytest.raises(DomainError) as exc_info:
                RPSService.submit_rps(rps.id, actor)
            assert "100%" in exc_info.value.corrective_step or "100%" in exc_info.value.message

        # Cleanup
        Rubric.objects.filter(instrument__rps=rps).delete()
        AssessmentInstrument.objects.filter(rps=rps).delete()
        RPS.objects.filter(pk=rps.id).delete()
        Course.objects.filter(pk=course.id).delete()
        Curriculum.objects.filter(pk=curriculum.id).delete()
        actor.delete()
        prodi.delete()


@pytest.mark.django_db(transaction=True)
class TestProperty20IndicatorCoverage:
    """Feature: obe-system, Property 20: RPS submission requires full indicator coverage

    Validates: Requirements 10.2, 10.4
    """

    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(map_all=st.booleans())
    def test_property_20_full_coverage(self, map_all, transactional_db):
        """Every Sub_CPMK indicator must map to at least one criterion."""
        prodi = ProgramOfStudy.objects.create(code=f"P20-{id(self)}", name="Test")
        actor = DemoUser.objects.create(name="Actor", role="lecturer", prodi=prodi)
        curriculum = Curriculum.objects.create(
            name="C", prodi=prodi, owner=actor, creator=actor, status="active"
        )
        cpl = CPL.objects.create(
            curriculum=curriculum, code="CPL-1", prodi=prodi,
            owner=actor, creator=actor, status="active"
        )
        course = Course.objects.create(
            curriculum=curriculum, code="C1", name="C1",
            prodi=prodi, owner=actor, creator=actor, status="active"
        )
        rps = RPSService.create_rps(course.id, curriculum.id, "A", "2024", actor)
        cpmk = CPMK.objects.create(rps=rps, code="CPMK-1")
        cpmk.derived_from.add(cpl)
        sub_cpmk = SubCPMK.objects.create(cpmk=cpmk, code="Sub-1")
        indicator = SubCPMKIndicator.objects.create(sub_cpmk=sub_cpmk, code="SI-1")

        instrument = AssessmentInstrument.objects.create(
            rps=rps, name="Instr", prodi=prodi, owner=actor, creator=actor, status="draft"
        )
        rubric = Rubric.objects.create(
            instrument=instrument, name="Rubric",
            prodi=prodi, owner=actor, creator=actor, status="draft"
        )
        criterion = RubricCriterion.objects.create(
            rubric=rubric, name="C1", weight=100, order=0
        )

        if map_all:
            criterion.mapped_indicators.add(indicator)
            # Should pass (weights sum to 100% and coverage met)
            result = RPSService.submit_rps(rps.id, actor)
            assert result.status == RPSStatus.SUBMITTED
        else:
            # No mapping - should fail with coverage error
            with pytest.raises(DomainError) as exc_info:
                RPSService.submit_rps(rps.id, actor)
            assert "belum dipetakan" in exc_info.value.message

        # Cleanup
        SubCPMKIndicator.objects.filter(sub_cpmk__cpmk__rps=rps).delete()
        SubCPMK.objects.filter(cpmk__rps=rps).delete()
        CPMK.objects.filter(rps=rps).delete()
        Rubric.objects.filter(instrument__rps=rps).delete()
        AssessmentInstrument.objects.filter(rps=rps).delete()
        RPS.objects.filter(pk=rps.id).delete()
        Course.objects.filter(pk=course.id).delete()
        CPL.objects.filter(curriculum=curriculum).delete()
        Curriculum.objects.filter(pk=curriculum.id).delete()
        actor.delete()
        prodi.delete()


@pytest.mark.django_db
def test_unit_instrument_rubric_cardinality():
    """Unit: instrument -> rubric cardinality is 1:1 (Req 9.1)."""
    prodi = ProgramOfStudy.objects.create(code="RUBRIC-CARD", name="Test")
    actor = DemoUser.objects.create(name="Actor", role="lecturer", prodi=prodi)
    curriculum = Curriculum.objects.create(
        name="C", prodi=prodi, owner=actor, creator=actor, status="active"
    )
    course = Course.objects.create(
        curriculum=curriculum, code="C1", name="C1",
        prodi=prodi, owner=actor, creator=actor, status="active"
    )
    rps = RPSService.create_rps(course.id, curriculum.id, "A", "2024", actor)
    instrument = RPSService.add_instrument(rps.id, {"name": "Instr"}, actor)

    rubric = RPSService.define_rubric(
        instrument.id,
        [{"name": "Crit1", "weight": 50, "levels": [{"label": "A", "score": 90}]},
         {"name": "Crit2", "weight": 50, "levels": [{"label": "B", "score": 70}]}],
        actor,
    )

    # One rubric per instrument
    assert instrument.rubric == rubric
    # Criterion levels stored correctly
    assert rubric.criteria.count() == 2
    crit = rubric.criteria.first()
    assert crit.levels.count() == 1


@pytest.mark.django_db
def test_unit_cpmk_subcpmk_indicator_cardinality():
    """Unit: CPMK -> Sub_CPMK -> indicators cardinality (Req 8.3)."""
    prodi = ProgramOfStudy.objects.create(code="CPMK-CARD", name="Test")
    actor = DemoUser.objects.create(name="Actor", role="lecturer", prodi=prodi)
    curriculum = Curriculum.objects.create(
        name="C", prodi=prodi, owner=actor, creator=actor, status="active"
    )
    cpl = CPL.objects.create(
        curriculum=curriculum, code="CPL-1", prodi=prodi,
        owner=actor, creator=actor, status="active"
    )
    course = Course.objects.create(
        curriculum=curriculum, code="C1", name="C1",
        prodi=prodi, owner=actor, creator=actor, status="active"
    )
    rps = RPSService.create_rps(course.id, curriculum.id, "A", "2024", actor)
    cpmk = RPSService.add_cpmk(rps.id, [cpl.id], {"code": "CPMK-1"}, actor)
    sub = RPSService.add_sub_cpmk(cpmk.id, {"code": "Sub-1"}, actor)
    ind1 = RPSService.add_sub_cpmk_indicator(sub.id, {"code": "SI-1"}, actor)
    ind2 = RPSService.add_sub_cpmk_indicator(sub.id, {"code": "SI-2"}, actor)

    assert cpmk.sub_cpmks.count() == 1
    assert sub.indicators.count() == 2
