"""Property test for soft dependencies (Task 2.7).

Feature: obe-system, Property 10: Soft dependencies advise but never block.

**Validates: Requirements 3.3**
"""

from __future__ import annotations

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from hypothesis.extra.django import TestCase

from timeline.models import DependencyKind, TaskStatus, TaskDependency
from timeline.services import TimelineService

from . import factories

pytestmark = pytest.mark.property

_non_selesai = st.sampled_from(
    [s for s in TaskStatus.values if s != TaskStatus.SELESAI]
)


class SoftDependencyProperty(TestCase):
    @settings(max_examples=100, deadline=None,
              suppress_health_check=[HealthCheck.too_slow])
    @given(pred_status=_non_selesai)
    def test_property_10_soft_deps_advise_never_block(self, pred_status):
        """Feature: obe-system, Property 10: Soft dependencies advise but never block."""
        instance = factories.make_instance()
        pred = factories.add_task(instance, status=pred_status)
        succ = factories.add_task(instance, status=TaskStatus.SIAP_DIKERJAKAN)
        TaskDependency.objects.create(
            predecessor=pred, successor=succ, kind=DependencyKind.SOFT
        )

        # Work is allowed despite the incomplete soft predecessor.
        dto = TimelineService.transition_to_dikerjakan(succ.id)
        succ.refresh_from_db()
        assert succ.status == TaskStatus.DIKERJAKAN

        # And an advisory naming the incomplete predecessor is surfaced.
        assert dto.advisories
        assert any(pred.title in advisory for advisory in dto.advisories)
