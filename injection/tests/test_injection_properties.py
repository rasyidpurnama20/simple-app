"""Property-based tests for the Data_Injection_Tool.

Feature: obe-system
Properties 3, 27.
"""

import pytest
from hypothesis import given, settings, strategies as st, HealthCheck

from core.models import DataInjectionLog, DemoUser, ProgramOfStudy
from injection.services import InjectionService


@pytest.mark.django_db(transaction=True)
class TestProperty27Idempotent:
    """Feature: obe-system, Property 27: Data injection is idempotent

    Validates: Requirements 17.2
    """

    @settings(max_examples=5, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(runs=st.integers(min_value=2, max_value=3))
    def test_property_27_idempotent(self, runs, transactional_db):
        """Running seed_demo_data multiple times yields identical data."""
        from curriculum.models import Curriculum
        from timeline.models import OBECycle

        # Reset first
        InjectionService.reset_demo_data()

        # Run seed
        InjectionService.seed_demo_data()
        count_after_first_curricula = Curriculum.objects.count()
        count_after_first_cycles = OBECycle.objects.count()

        # Run again (idempotent)
        for _ in range(runs - 1):
            InjectionService.seed_demo_data()

        count_after_repeat_curricula = Curriculum.objects.count()
        count_after_repeat_cycles = OBECycle.objects.count()

        # Same data after repeated runs
        assert count_after_first_curricula == count_after_repeat_curricula
        assert count_after_first_cycles == count_after_repeat_cycles


@pytest.mark.django_db
def test_unit_injection_writes_log():
    """Unit: data injection writes a log record (Req 17.3)."""
    initial_count = DataInjectionLog.objects.count()
    InjectionService.seed_demo_data()
    assert DataInjectionLog.objects.count() > initial_count


@pytest.mark.django_db(transaction=True)
class TestProperty3ProductionReadiness:
    """Feature: obe-system, Property 3: Production-readiness fields are always populated

    Validates: Requirements 1.3, 6.3, 8.4, 9.4
    """

    def test_property_3_fields_populated(self, transactional_db):
        """All business entities have production-readiness fields populated."""
        from curriculum.models import Curriculum, CPL, Course
        from rps.models import RPS, AssessmentInstrument, Rubric
        from timeline.models import OBECycle

        InjectionService.reset_demo_data()
        InjectionService.seed_demo_data()

        # Check OBECycle
        for cycle in OBECycle.objects.all():
            assert cycle.prodi is not None
            assert cycle.owner is not None
            assert cycle.creator is not None
            assert cycle.status
            assert cycle.version >= 1
            assert cycle.created_time is not None
            assert cycle.modified_time is not None

        # Check Curriculum
        for curr in Curriculum.objects.all():
            assert curr.prodi is not None
            assert curr.owner is not None
            assert curr.creator is not None
            assert curr.status
            assert curr.version >= 1

        # Check CPL
        for cpl in CPL.objects.all():
            assert cpl.prodi is not None
            assert cpl.owner is not None
            assert cpl.creator is not None

        # Check Course
        for course in Course.objects.all():
            assert course.prodi is not None
            assert course.owner is not None
            assert course.creator is not None

        # Check RPS
        for rps in RPS.objects.all():
            assert rps.prodi is not None
            assert rps.owner is not None
            assert rps.creator is not None

        # Check AssessmentInstrument
        for instr in AssessmentInstrument.objects.all():
            assert instr.prodi is not None
            assert instr.owner is not None
            assert instr.creator is not None

        # Check Rubric
        for rubric in Rubric.objects.all():
            assert rubric.prodi is not None
            assert rubric.owner is not None
            assert rubric.creator is not None
