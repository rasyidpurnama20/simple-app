"""Property-based tests for explainable validation messages.

Feature: obe-system, Property 25: Validation messages are plain-language and
actionable.

**Validates: Requirements 14.2, 14.3**
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from core.exceptions import DomainError
from core.validators import (
    JARGON_BLOCKLIST,
    build_domain_error,
    find_jargon,
    format_validation_message,
)

# Plain-language text that deliberately avoids blocklisted jargon. We build
# fragments from safe words so the generated problem/corrective step read like
# real user-facing guidance without internal-system terminology.
_SAFE_WORDS = [
    "template", "phase", "milestone", "task", "deadline", "curriculum",
    "outcome", "indicator", "rubric", "weight", "score", "reason",
    "add", "choose", "complete", "review", "select", "please", "missing",
    "the", "a", "at", "least", "one", "must", "first", "then", "value",
]

_safe_text = st.lists(st.sampled_from(_SAFE_WORDS), min_size=2, max_size=12).map(
    lambda words: " ".join(words)
)


@pytest.mark.property
@settings(max_examples=150, deadline=None)
@given(problem=_safe_text, corrective=_safe_text)
def test_property_25_messages_are_plain_and_actionable(problem, corrective):
    """A built DomainError states problem + corrective step, free of jargon."""
    error = build_domain_error(problem, corrective)

    # States the problem AND the corrective step (Requirement 14.2).
    assert problem in error.full_message
    assert corrective in error.full_message
    assert error.message
    assert error.corrective_step

    # Contains no database / internal-system terminology (Requirement 14.3).
    assert find_jargon(error.full_message) == []


@pytest.mark.property
@settings(max_examples=100, deadline=None)
@given(jargon_term=st.sampled_from(JARGON_BLOCKLIST), safe=_safe_text)
def test_property_25_jargon_is_rejected_before_reaching_users(jargon_term, safe):
    """Messages containing internal-system terminology are never emitted."""
    with pytest.raises(ValueError):
        build_domain_error(f"{safe} {jargon_term}", safe)


def test_format_validation_message_requires_both_parts():
    """Both a problem and a corrective step are mandatory (Requirement 14.2)."""
    with pytest.raises(ValueError):
        format_validation_message("", "do something")
    with pytest.raises(ValueError):
        format_validation_message("something wrong", "")


def test_domain_error_full_message_combines_parts():
    """DomainError.full_message joins problem and corrective step."""
    err = DomainError("The template has no phase.", "Add at least one phase.")
    assert err.full_message == "The template has no phase. Add at least one phase."
