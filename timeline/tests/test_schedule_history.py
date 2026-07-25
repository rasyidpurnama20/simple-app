"""Property test for non-destructive schedule history (Task 2.11).

Feature: obe-system, Property 14: Schedule history is non-destructive and ordered.

**Validates: Requirements 5.1, 5.2, 5.3, 5.4**
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


class ScheduleHistoryProperty(TestCase):
    @settings(max_examples=100, deadline=None,
              suppress_health_check=[HealthCheck.too_slow])
    @given(deltas=st.lists(st.integers(min_value=-30, max_value=30),
                           min_size=1, max_size=6))
    def test_property_14_history_non_destructive_and_ordered(self, deltas):
        """Feature: obe-system, Property 14: Schedule history is non-destructive and ordered."""
        instance = factories.make_instance()
        phase = Phase.objects.create(instance=instance, name="P")
        milestone = Milestone.objects.create(phase=phase, name="M")
        start = date(2025, 1, 1)
        task = Task.objects.create(
            milestone=milestone, title="T",
            deadline_kind=DeadlineKind.FIXED, fixed_date=start,
            resolved_deadline=start,
        )
        actor = factories.make_user()

        prev = start
        expected_pairs = []  # (previous, new)
        for d in deltas:
            new_val = prev + timedelta(days=d)
            TimelineService.change_schedule(
                "task", task.id, new_val, reason=f"alasan {d}", actor=actor
            )
            expected_pairs.append((prev, new_val))
            prev = new_val

        history = TimelineService.get_history(instance.id)
        # One record per change; nothing is overwritten (Requirement 5.1).
        assert len(history) == len(deltas)

        # Newest-first ordering (Requirement 5.4).
        timestamps = [(h.timestamp, h.id) for h in history]
        assert timestamps == sorted(timestamps, reverse=True)

        # Every record retains actor, reason, previous and new values (5.2, 5.3).
        for entry in history:
            assert entry.actor_name == actor.name
            assert entry.reason
        recorded_pairs = {(h.previous_value, h.new_value) for h in history}
        for pair in expected_pairs:
            assert pair in recorded_pairs


@pytest.mark.django_db
def test_change_schedule_requires_reason():
    """A schedule change without a reason is rejected (Requirement 5.2)."""
    from core.exceptions import DomainError

    instance = factories.make_instance()
    phase = Phase.objects.create(instance=instance, name="P")
    milestone = Milestone.objects.create(phase=phase, name="M",
                                          milestone_date=date(2025, 1, 1))
    with pytest.raises(DomainError):
        TimelineService.change_schedule(
            "milestone", milestone.id, date(2025, 2, 1), reason="  ", actor=None
        )
