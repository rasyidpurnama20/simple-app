"""Property-based tests for the Curriculum_Module.

Feature: obe-system
Properties 15, 16, 17.
"""

import pytest
from hypothesis import given, settings, strategies as st, HealthCheck

from core.exceptions import DomainError
from core.models import DemoUser, ProgramOfStudy
from curriculum.models import (
    ContributionLevel,
    CourseCPLContribution,
    CPL,
    Course,
    Curriculum,
    CurriculumStatus,
)
from curriculum.services import CurriculumService


@pytest.fixture
def prodi(db):
    return ProgramOfStudy.objects.create(code="TEST-PRODI", name="Test Prodi")


@pytest.fixture
def actor(db, prodi):
    return DemoUser.objects.create(name="Test User", role="kaprodi", prodi=prodi)


@pytest.mark.django_db(transaction=True)
class CurriculumLifecycleProperties:
    """Feature: obe-system, Property 15: At most one active curriculum per prodi
    Feature: obe-system, Property 16: Curriculum status stays within its lifecycle
    """
    pass


@pytest.mark.django_db(transaction=True)
class TestProperty15SingleActiveCurriculum:
    """Feature: obe-system, Property 15: At most one active curriculum per prodi

    Validates: Requirements 6.4, 6.5
    """

    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(n=st.integers(min_value=2, max_value=5))
    def test_property_15_at_most_one_active_per_prodi(self, n, transactional_db):
        """For any sequence of curriculum activations within a prodi,
        at most one Curriculum is active at any time."""
        prodi = ProgramOfStudy.objects.create(
            code=f"P15-{n}-{id(self)}", name="Test"
        )
        actor = DemoUser.objects.create(name="Actor", role="kaprodi", prodi=prodi)

        curricula = []
        for i in range(n):
            c = CurriculumService.create_curriculum(
                {"name": f"Curriculum {i}", "prodi": prodi}, actor
            )
            curricula.append(c)

        # Activate the first one
        CurriculumService.activate_curriculum(curricula[0].id, actor)

        # Try to activate the second — should be rejected
        with pytest.raises(DomainError) as exc_info:
            CurriculumService.activate_curriculum(curricula[1].id, actor)

        assert "sudah memiliki kurikulum aktif" in exc_info.value.message

        # Verify at most one is active
        active_count = Curriculum.objects.filter(
            prodi=prodi, status=CurriculumStatus.ACTIVE
        ).count()
        assert active_count <= 1

        # Cleanup
        Curriculum.objects.filter(prodi=prodi).delete()
        actor.delete()
        prodi.delete()


@pytest.mark.django_db(transaction=True)
class TestProperty16CurriculumLifecycle:
    """Feature: obe-system, Property 16: Curriculum status stays within its lifecycle

    Validates: Requirements 6.6
    """

    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(status_seed=st.sampled_from(["draft", "active", "archived"]))
    def test_property_16_status_within_lifecycle(self, status_seed, transactional_db):
        """Curriculum status is always one of draft, active, or archived."""
        prodi = ProgramOfStudy.objects.create(
            code=f"P16-{status_seed}-{id(self)}", name="Test"
        )
        actor = DemoUser.objects.create(name="Actor", role="kaprodi", prodi=prodi)

        c = CurriculumService.create_curriculum({"name": "Test", "prodi": prodi}, actor)
        assert c.status == CurriculumStatus.DRAFT

        valid_statuses = {s.value for s in CurriculumStatus}
        assert c.status in valid_statuses

        # Activate
        CurriculumService.activate_curriculum(c.id, actor)
        c.refresh_from_db()
        assert c.status in valid_statuses

        # Archive
        CurriculumService.archive_curriculum(c.id, actor)
        c.refresh_from_db()
        assert c.status in valid_statuses

        # Cannot re-activate archived
        with pytest.raises(DomainError):
            CurriculumService.activate_curriculum(c.id, actor)

        # Cleanup
        Curriculum.objects.filter(prodi=prodi).delete()
        actor.delete()
        prodi.delete()


@pytest.mark.django_db(transaction=True)
class TestProperty17ContributionLevel:
    """Feature: obe-system, Property 17: Contribution level is constrained

    Validates: Requirements 7.1, 7.4
    """

    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(level=st.text(min_size=1, max_size=20))
    def test_property_17_contribution_constrained(self, level, transactional_db):
        """For any Course-to-CPL mapping, the contribution level must be one of
        Introduce, Reinforce, or Master."""
        valid_levels = {c.value for c in ContributionLevel}

        prodi = ProgramOfStudy.objects.create(
            code=f"P17-{id(self)}", name="Test"
        )
        actor = DemoUser.objects.create(name="Actor", role="kaprodi", prodi=prodi)
        curriculum = Curriculum.objects.create(
            name="C", prodi=prodi, owner=actor, creator=actor, status="draft"
        )
        cpl = CPL.objects.create(
            curriculum=curriculum, code="CPL-1", prodi=prodi,
            owner=actor, creator=actor, status="draft"
        )
        course = Course.objects.create(
            curriculum=curriculum, code="CS101", name="Course 1",
            prodi=prodi, owner=actor, creator=actor, status="draft"
        )

        if level in valid_levels:
            result = CurriculumService.map_course_to_cpl(course.id, cpl.id, level, actor)
            assert result.contribution_level in valid_levels
        else:
            with pytest.raises(DomainError) as exc_info:
                CurriculumService.map_course_to_cpl(course.id, cpl.id, level, actor)
            # Error message lists valid values
            for v in valid_levels:
                assert v in exc_info.value.corrective_step

        # Cleanup
        CourseCPLContribution.objects.filter(course=course).delete()
        course.delete()
        cpl.delete()
        curriculum.delete()
        actor.delete()
        prodi.delete()


@pytest.mark.django_db
def test_unit_curriculum_cpl_indicator_cardinality():
    """Unit: curriculum -> CPL -> indicator cardinality (Req 6.1)."""
    prodi = ProgramOfStudy.objects.create(code="CARD-TEST", name="Test")
    actor = DemoUser.objects.create(name="Actor", role="kaprodi", prodi=prodi)

    curriculum = CurriculumService.create_curriculum(
        {"name": "Test Curriculum", "prodi": prodi}, actor
    )
    cpl = CurriculumService.add_cpl(
        curriculum.id, {"code": "CPL-01", "description": "Test"}, actor
    )
    ind1 = CurriculumService.add_cpl_indicator(
        cpl.id, {"code": "IK-01", "target_value": 80}, actor
    )
    ind2 = CurriculumService.add_cpl_indicator(
        cpl.id, {"code": "IK-02", "target_value": 75}, actor
    )

    assert cpl.indicators.count() == 2
    assert ind1.cpl == cpl
    assert ind2.cpl == cpl


@pytest.mark.django_db
def test_unit_many_to_many_course_cpl():
    """Unit: many-to-many course <-> CPL (Reqs 7.2, 7.3)."""
    prodi = ProgramOfStudy.objects.create(code="M2M-TEST", name="Test")
    actor = DemoUser.objects.create(name="Actor", role="kaprodi", prodi=prodi)

    curriculum = CurriculumService.create_curriculum(
        {"name": "Test", "prodi": prodi}, actor
    )
    cpl1 = CurriculumService.add_cpl(curriculum.id, {"code": "CPL-A"}, actor)
    cpl2 = CurriculumService.add_cpl(curriculum.id, {"code": "CPL-B"}, actor)
    course1 = CurriculumService.add_course(curriculum.id, {"code": "C1", "name": "Course 1"}, actor)
    course2 = CurriculumService.add_course(curriculum.id, {"code": "C2", "name": "Course 2"}, actor)

    # Course 1 -> both CPLs
    CurriculumService.map_course_to_cpl(course1.id, cpl1.id, "Introduce", actor)
    CurriculumService.map_course_to_cpl(course1.id, cpl2.id, "Master", actor)
    # Course 2 -> CPL 1
    CurriculumService.map_course_to_cpl(course2.id, cpl1.id, "Reinforce", actor)

    # A course can contribute to multiple CPLs
    assert course1.cpl_contributions.count() == 2
    # A CPL can be contributed to by multiple courses
    assert cpl1.course_contributions.count() == 2
