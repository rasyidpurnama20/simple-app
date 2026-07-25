"""Explainable validation utilities (Requirements 14.2, 14.3).

These helpers format validation messages so they always state the *problem*
and a *corrective step* in plain language, and never leak database or
internal-system terminology (no "foreign key", "constraint", "null", table
names, etc.). The service layer uses `build_domain_error` to construct
`DomainError` instances that are guaranteed plain-language.
"""

from __future__ import annotations

from typing import Iterable

from .exceptions import DomainError

# Words / phrases that betray database or internal-system implementation
# details. Validation messages shown to users must contain none of these
# (Requirement 14.3). Matching is case-insensitive and substring-based.
JARGON_BLOCKLIST: tuple[str, ...] = (
    "foreign key",
    "constraint",
    "null",
    "not-null",
    "not null",
    "primary key",
    "unique index",
    "database",
    "table",
    "column",
    "schema",
    "sql",
    "queryset",
    "orm",
    "integrityerror",
    "valueerror",
    "traceback",
    "exception",
    "stack trace",
    "nonetype",
)


def find_jargon(text: str) -> list[str]:
    """Return the list of blocklisted jargon terms present in ``text``.

    An empty list means the text is free of internal-system terminology.
    """
    lowered = text.lower()
    return [term for term in JARGON_BLOCKLIST if term in lowered]


def contains_jargon(text: str) -> bool:
    """True if ``text`` contains any blocklisted internal-system terminology."""
    return bool(find_jargon(text))


def format_validation_message(problem: str, corrective_step: str) -> str:
    """Combine a problem and a corrective step into one plain-language string.

    Both parts are required so every rejection tells the user what went wrong
    *and* what to do about it (Requirement 14.2).
    """
    problem = (problem or "").strip()
    corrective_step = (corrective_step or "").strip()
    if not problem:
        raise ValueError("A validation message must describe the problem.")
    if not corrective_step:
        raise ValueError("A validation message must include a corrective step.")
    return f"{problem} {corrective_step}"


def build_domain_error(problem: str, corrective_step: str) -> DomainError:
    """Construct a plain-language ``DomainError``.

    Guards (in development) against accidentally leaking internal-system
    terminology into user-facing messages.
    """
    combined = format_validation_message(problem, corrective_step)
    leaked = find_jargon(combined)
    if leaked:
        # Defensive: never surface jargon to end users. In development we fail
        # loudly so the message can be rewritten in plain language.
        raise ValueError(
            "Validation message contains internal-system terminology: "
            f"{', '.join(leaked)}"
        )
    return DomainError(problem.strip(), corrective_step.strip())


def assert_plain_language(messages: Iterable[str]) -> None:
    """Raise ``AssertionError`` if any message contains blocklisted jargon.

    Useful in tests to guarantee messages stay plain-language (Property 25).
    """
    for message in messages:
        leaked = find_jargon(message)
        assert not leaked, (
            f"Message contains internal-system terminology {leaked!r}: {message!r}"
        )
