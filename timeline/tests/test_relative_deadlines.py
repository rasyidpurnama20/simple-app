"""Property test for relative deadlines (Task 2.9).

Feature: obe-system, Property 11: Relative deadlines track their reference.

**Validates: Requirements 3.5**
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from hypothesis.extra.django import TestCase

from timeline.models import DeadlineKind, Milestone, Phase, Task
from timeline.services import TimelineService

from . import factories

pytestmark = pytest.mark.property


class RelativeDeadlineProperty(TestCase):
    @settings(max_examples=100, deadline=None,
              suppress_health_check=[HealthCheck.too_slow])
    @given(
        base_offset=st.integers(min_value=-200, max_value=200),
        rel_offset=st.integers(min_value=-30, max_value=30),
        delta=st.integers(min_value=-60, max_value=60),
    )
    def test_property_11_relative_deadline_tracks_reference(
        self, base_offset, rel_offset, delta
    ):
        """Feature: obe-system, Property 11: Relative deadlines track their reference."""
        instance = factories.make_instance()
        phase = Phase.objects.create(instance=instance, name="P")
        base_date = date(2025, 1, 1) + timedelta(days=base_offset)
        milestone = Milestone.objects.create(
            phase=phase, name="M", milestone_date=base_date
        )
        task = Task.objects.create(
            milestone=milestone, title="T",
            deadline_kind=DeadlineKind.RELATIVE,
            relative_offset_days=rel_offset,
            relative_reference_milestone=milestone,
        )

        TimelineService.recompute_relative_deadlines(instance.id)
        task.refresh_from_db()
        expected = base_date + timedelta(days=rel_offset)
        assert task.resolved_deadline == expected

        # Shifting the reference by delta shifts the resolved deadline by delta.
        new_date = base_date + timedelta(days=delta)
        TimelineService.change_schedule(
            "milestone", milestone.id, new_date, reason="penyesuaian", actor=None
        )
        task.refresh_from_db()
        assert task.resolved_deadline == expected + timedelta(days=delta)
