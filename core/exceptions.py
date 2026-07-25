"""Shared domain exceptions for the OBE_System.

`DomainError` is the single exception type raised by the service layer for any
business-rule rejection. Views catch it and render a plain-language error
fragment. It always carries both a `message` (the problem) and a
`corrective_step` (what the user should do), per Requirements 14.2 and 14.3.
"""

from __future__ import annotations


class DomainError(Exception):
    """A business-rule violation expressed in plain language.

    Attributes:
        message: A plain-language statement of the problem.
        corrective_step: A plain-language statement of how to fix it.
    """

    def __init__(self, message: str, corrective_step: str):
        self.message = message
        self.corrective_step = corrective_step
        super().__init__(self.full_message)

    @property
    def full_message(self) -> str:
        """A single combined string of problem + corrective step."""
        return f"{self.message} {self.corrective_step}".strip()

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"DomainError(message={self.message!r}, "
            f"corrective_step={self.corrective_step!r})"
        )
