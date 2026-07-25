"""Property and edge tests for template instantiation (Task 2.3).

Feature: obe-system, Property 1: Instantiation preserves template structure.
Feature: obe-system, Property 2: Each instance binds to exactly one cycle.
Edge: reject a template with no phase (Requirement 1.5).

**Validates: Requirements 1.1, 1.2, 1.4, 1.5**
"""

from __future__ import annotations

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from hypothesis.extra.django import TestCase

from core.exceptions import DomainError
from timeline.models import (
    ChecklistItem,
    Milestone,
    Phase,
    Task,
    TaskDependency,
    TimelineInstance,
    TimelineTemplate,
)
from timeline.services import TimelineService

from . import factories

pytestmark = pytest.mark.property

# A nested structure: list of phases -> list of milestones -> task count.
_structure = st.lists(
    st.lists(st.integers(min_value=0, max_value=3), min_size=1, max_size=3),
    min_size=1,
    max_size=3,
)


class InstantiationProperties(TestCase):
    def _make_edges(self, data, n_tasks):
        edges = set()
        if n_tasks >= 2:
            n_edges = data.draw(st.integers(min_value=0, max_value=min(n_tasks, 4)))
            for _ in range(n_edges):
                i = data.draw(st.integers(min_value=0, max_value=n_tasks - 2))
                j = data.draw(st.integers(min_value=i + 1, max_value=n_tasks - 1))
                kind = data.draw(st.sampled_from(["hard", "soft"]))
                edges.add((i, j, kind))
        return sorted(edges)

    @settings(max_examples=100, deadline=None,
              suppress_health_check=[HealthCheck.too_slow])
    @given(structure=_structure, data=st.data())
    def test_property_1_instantiation_preserves_structure(self, structure, data):
        """Feature: obe-system, Property 1: Instantiation preserves template structure."""
        n_tasks = sum(sum(phase) for phase in structure)
        edges = self._make_edges(data, n_tasks)

        template, _ = factories.build_template(
            structure, checklist_per_task=2, edges=edges
        )
        actor = factories.make_user()

        exp_phases = len(structure)
        exp_milestones = sum(len(phase) for phase in structure)
        exp_tasks = n_tasks
        exp_checklist = exp_tasks * 2
        exp_deps = len(edges)

        dto = TimelineService.create_cycle_from_template(
            template.id, {"name": "C"}, actor
        )

        # DTO counts mirror the template exactly.
        assert dto.phase_count == exp_phases
        assert dto.milestone_count == exp_milestones
        assert dto.task_count == exp_tasks
        assert dto.dependency_count == exp_deps

        # And the persisted instance rows mirror the template exactly.
        instance = TimelineInstance.objects.get(pk=dto.instance_id)
        assert instance.phases.count() == exp_phases
        assert Milestone.objects.filter(phase__instance=instance).count() == exp_milestones
        inst_tasks = Task.objects.filter(milestone__phase__instance=instance)
        assert inst_tasks.count() == exp_tasks
        assert ChecklistItem.objects.filter(task__in=inst_tasks).count() == exp_checklist
        assert TaskDependency.objects.filter(predecessor__in=inst_tasks).count() == exp_deps

    @settings(max_examples=100, deadline=None,
              suppress_health_check=[HealthCheck.too_slow])
    @given(structure=_structure)
    def test_property_2_instance_binds_to_exactly_one_cycle(self, structure):
        """Feature: obe-system, Property 2: Each instance binds to exactly one cycle."""
        template, _ = factories.build_template(structure, checklist_per_task=0)
        actor = factories.make_user()

        dto = TimelineService.create_cycle_from_template(
            template.id, {"name": "C"}, actor
        )
        instance = TimelineInstance.objects.get(pk=dto.instance_id)
        # Exactly one cycle is referenced, and it is the one just created.
        assert instance.cycle_id == dto.cycle_id
        assert TimelineInstance.objects.filter(cycle_id=dto.cycle_id).count() == 1


@pytest.mark.django_db
def test_edge_reject_template_without_phase():
    """A template with no phase is rejected before any write (Requirement 1.5)."""
    template = TimelineTemplate.objects.create(name="Kosong")
    actor = factories.make_user()
    instances_before = TimelineInstance.objects.count()

    with pytest.raises(DomainError) as exc:
        TimelineService.create_cycle_from_template(template.id, {"name": "C"}, actor)

    # No instance was written, and the message is explainable.
    assert TimelineInstance.objects.count() == instances_before
    assert exc.value.message and exc.value.corrective_step
