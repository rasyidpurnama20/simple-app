"""Property and example tests for the task status lifecycle (Task 2.5).

Feature: obe-system, Property 4: Task status is always a valid enum value.
Feature: obe-system, Property 5: Belum Siap while a hard dependency is incomplete.
Feature: obe-system, Property 6: Siap Dikerjakan when all hard dependencies complete.
Feature: obe-system, Property 7: Overdue incomplete tasks become Terlambat.
Feature: obe-system, Property 8: Selesai only when marked complete and all checklist items complete.
Feature: obe-system, Property 9: Hard dependencies block Dikerjakan.
Example: submit -> Diajukan (2.4), return -> Perlu Revisi (2.5).

**Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 3.2**
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from hypothesis.extra.django import TestCase

from core.exceptions import DomainError
from timeline.models import DependencyKind, Task, TaskDependency, TaskStatus
from timeline.services import TimelineService

from . import factories

pytestmark = pytest.mark.property

_TODAY = date(2025, 6, 15)
_FUTURE = _TODAY + timedelta(days=30)
_PAST = _TODAY - timedelta(days=30)

_non_selesai = st.sampled_from(
    [s for s in TaskStatus.values if s != TaskStatus.SELESAI]
)


class TaskStatusProperties(TestCase):
    @settings(max_examples=100, deadline=None,
              suppress_health_check=[HealthCheck.too_slow])
    @given(pred_status=_non_selesai)
    def test_property_5_incomplete_hard_dep_is_belum_siap(self, pred_status):
        """Feature: obe-system, Property 5: Belum Siap while a hard dependency is incomplete."""
        instance = factories.make_instance()
        pred = factories.add_task(instance, status=pred_status)
        succ = factories.add_task(instance, status=TaskStatus.SIAP_DIKERJAKAN,
                                  resolved_deadline=_FUTURE)
        TaskDependency.objects.create(
            predecessor=pred, successor=succ, kind=DependencyKind.HARD
        )
        TimelineService.recompute_statuses(instance.id, today=_TODAY)
        succ.refresh_from_db()
        # Predecessor is not Selesai, so the successor must be Belum Siap.
        assert succ.status == TaskStatus.BELUM_SIAP

    @settings(max_examples=100, deadline=None,
              suppress_health_check=[HealthCheck.too_slow])
    @given(start_status=st.sampled_from(
        [TaskStatus.BELUM_SIAP, TaskStatus.SIAP_DIKERJAKAN, TaskStatus.TERLAMBAT]))
    def test_property_6_all_hard_deps_complete_is_siap(self, start_status):
        """Feature: obe-system, Property 6: Siap Dikerjakan when all hard dependencies complete."""
        instance = factories.make_instance()
        pred = factories.add_task(instance, status=TaskStatus.SELESAI)
        succ = factories.add_task(instance, status=start_status,
                                  resolved_deadline=_FUTURE)
        TaskDependency.objects.create(
            predecessor=pred, successor=succ, kind=DependencyKind.HARD
        )
        TimelineService.recompute_statuses(instance.id, today=_TODAY)
        succ.refresh_from_db()
        assert succ.status == TaskStatus.SIAP_DIKERJAKAN

    @settings(max_examples=100, deadline=None,
              suppress_health_check=[HealthCheck.too_slow])
    @given(status=_non_selesai)
    def test_property_7_overdue_incomplete_is_terlambat(self, status):
        """Feature: obe-system, Property 7: Overdue incomplete tasks become Terlambat."""
        instance = factories.make_instance()
        task = factories.add_task(instance, status=status, resolved_deadline=_PAST)
        TimelineService.recompute_statuses(instance.id, today=_TODAY)
        task.refresh_from_db()
        assert task.status == TaskStatus.TERLAMBAT

    @settings(max_examples=100, deadline=None,
              suppress_health_check=[HealthCheck.too_slow])
    @given(structure=st.lists(
        st.lists(st.integers(min_value=1, max_value=2), min_size=1, max_size=2),
        min_size=1, max_size=2))
    def test_property_4_status_always_valid_enum(self, structure):
        """Feature: obe-system, Property 4: Task status is always a valid enum value."""
        template, _ = factories.build_template(structure, checklist_per_task=0)
        actor = factories.make_user()
        dto = TimelineService.create_cycle_from_template(template.id, {"name": "C"}, actor)
        TimelineService.recompute_statuses(dto.instance_id, today=_TODAY)
        statuses = Task.objects.filter(
            milestone__phase__instance_id=dto.instance_id
        ).values_list("status", flat=True)
        assert all(s in set(TaskStatus.values) for s in statuses)

    @settings(max_examples=100, deadline=None,
              suppress_health_check=[HealthCheck.too_slow])
    @given(n_items=st.integers(min_value=0, max_value=4),
           n_complete=st.integers(min_value=0, max_value=4))
    def test_property_8_selesai_iff_complete_and_checklist_done(self, n_items, n_complete):
        """Feature: obe-system, Property 8: Selesai only when marked complete and all checklist items complete."""
        instance = factories.make_instance()
        task = factories.add_task(instance, status=TaskStatus.DIKERJAKAN)
        n_complete = min(n_complete, n_items)
        from timeline.models import ChecklistItem
        for i in range(n_items):
            ChecklistItem.objects.create(
                task=task, text=f"i{i}", is_complete=(i < n_complete), order=i
            )
        all_done = (n_items == n_complete)
        if all_done:
            dto = TimelineService.complete_task(task.id)
            assert dto.status == TaskStatus.SELESAI
            task.refresh_from_db()
            assert task.status == TaskStatus.SELESAI and task.is_complete
        else:
            with pytest.raises(DomainError):
                TimelineService.complete_task(task.id)
            task.refresh_from_db()
            # Remains not Selesai when a checklist item is open.
            assert task.status != TaskStatus.SELESAI

    @settings(max_examples=100, deadline=None,
              suppress_health_check=[HealthCheck.too_slow])
    @given(pred_status=_non_selesai)
    def test_property_9_hard_dep_blocks_dikerjakan(self, pred_status):
        """Feature: obe-system, Property 9: Hard dependencies block Dikerjakan."""
        instance = factories.make_instance()
        pred = factories.add_task(instance, status=pred_status)
        succ = factories.add_task(instance, status=TaskStatus.SIAP_DIKERJAKAN)
        TaskDependency.objects.create(
            predecessor=pred, successor=succ, kind=DependencyKind.HARD
        )
        with pytest.raises(DomainError):
            TimelineService.transition_to_dikerjakan(succ.id)
        succ.refresh_from_db()
        assert succ.status != TaskStatus.DIKERJAKAN


@pytest.mark.django_db
def test_example_submit_sets_diajukan():
    """Submitting a task sets its status to Diajukan (Requirement 2.4)."""
    instance = factories.make_instance()
    task = factories.add_task(instance, status=TaskStatus.DIKERJAKAN)
    dto = TimelineService.submit_task(task.id)
    assert dto.status == TaskStatus.DIAJUKAN


@pytest.mark.django_db
def test_example_return_sets_perlu_revisi():
    """Returning a submitted task sets its status to Perlu Revisi (Requirement 2.5)."""
    instance = factories.make_instance()
    task = factories.add_task(instance, status=TaskStatus.DIAJUKAN)
    dto = TimelineService.return_task_for_revision(task.id)
    assert dto.status == TaskStatus.PERLU_REVISI
