"""Property tests for Home grouping and explanations (Task 2.13).

Feature: obe-system, Property 12: Home grouping maps status to the correct bucket.
Feature: obe-system, Property 13: Explanations are complete.

**Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5, 13.2, 14.1**
"""

from __future__ import annotations

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from hypothesis.extra.django import TestCase

from timeline.models import TaskStatus
from timeline.services import HomeService

from . import factories

pytestmark = pytest.mark.property

# Statuses that map into one of the three Home buckets (Property 12).
_GROUPED = [
    TaskStatus.SIAP_DIKERJAKAN,
    TaskStatus.DIKERJAKAN,
    TaskStatus.BELUM_SIAP,
    TaskStatus.DIAJUKAN,
]

_DO_NOW = {TaskStatus.SIAP_DIKERJAKAN, TaskStatus.DIKERJAKAN}
_NEXT = {TaskStatus.BELUM_SIAP}
_WAITING = {TaskStatus.DIAJUKAN}


class HomeGroupingProperties(TestCase):
    @settings(max_examples=100, deadline=None,
              suppress_health_check=[HealthCheck.too_slow])
    @given(statuses=st.lists(st.sampled_from(_GROUPED), min_size=1, max_size=8))
    def test_property_12_grouping_maps_status_to_bucket(self, statuses):
        """Feature: obe-system, Property 12: Home grouping maps status to the correct bucket."""
        user = factories.make_user()
        instance = factories.make_instance()
        created = []
        for status in statuses:
            task = factories.add_task(instance, status=status, owner=user)
            created.append((task.id, status))

        groups = HomeService.next_best_work(user.id)
        do_now_ids = {t.id for t in groups.do_now}
        next_ids = {t.id for t in groups.next}
        waiting_ids = {t.id for t in groups.waiting_on_others}

        # Each grouped task appears in exactly one bucket, the correct one.
        for task_id, status in created:
            buckets = [task_id in do_now_ids, task_id in next_ids, task_id in waiting_ids]
            assert sum(buckets) == 1
            if status in _DO_NOW:
                assert task_id in do_now_ids
            elif status in _NEXT:
                assert task_id in next_ids
            elif status in _WAITING:
                assert task_id in waiting_ids

    @settings(max_examples=100, deadline=None,
              suppress_health_check=[HealthCheck.too_slow])
    @given(
        status=st.sampled_from(_GROUPED),
        fill_explanations=st.booleans(),
    )
    def test_property_13_explanations_are_complete(self, status, fill_explanations):
        """Feature: obe-system, Property 13: Explanations are complete."""
        user = factories.make_user()
        instance = factories.make_instance()
        kwargs = {}
        if fill_explanations:
            kwargs = dict(
                explanation_what="w", explanation_why="y", explanation_who="o",
                explanation_when="n", explanation_how="h", explanation_next="x",
            )
        # else: all explanation fields blank -> defaults must fill them in.
        factories.add_task(instance, status=status, owner=user, **kwargs)

        groups = HomeService.next_best_work(user.id)
        all_tasks = groups.do_now + groups.next + groups.waiting_on_others
        assert all_tasks  # the task landed in some bucket
        for dto in all_tasks:
            assert dto.explanation.is_complete()
