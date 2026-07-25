"""Timeline_Engine result DTOs.

DTOs are the transport-agnostic return type of the service layer. Views (and a
future JSON API) consume these instead of ORM models (Requirement 18.4).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass(frozen=True)
class ExplanationDTO:
    """The complete six-facet explanation for a task (Property 13)."""

    what: str
    why: str
    who: str
    when: str
    how: str
    next: str

    def is_complete(self) -> bool:
        """True when every facet is populated with non-blank text."""
        return all(
            bool((value or "").strip())
            for value in (self.what, self.why, self.who, self.when, self.how, self.next)
        )


@dataclass(frozen=True)
class TaskDTO:
    """A task with its status, deadline, explanation, and any advisories."""

    id: int
    title: str
    status: str
    status_label: str
    owner_name: str | None
    resolved_deadline: date | None
    is_complete: bool
    explanation: ExplanationDTO
    advisories: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CycleDTO:
    """A created OBE cycle with its bound timeline instance."""

    cycle_id: int
    instance_id: int
    name: str
    academic_year: str
    phase_count: int
    milestone_count: int
    task_count: int
    dependency_count: int


@dataclass(frozen=True)
class ScheduleChangeDTO:
    """A single non-destructive schedule-history entry."""

    id: int
    target_kind: str  # "task" | "milestone"
    target_id: int
    target_name: str
    actor_name: str | None
    timestamp: datetime
    previous_value: date | None
    new_value: date | None
    reason: str


@dataclass(frozen=True)
class HomeGroupsDTO:
    """The Home next-best-work partition (Requirements 4.1-4.5)."""

    do_now: list[TaskDTO] = field(default_factory=list)
    next: list[TaskDTO] = field(default_factory=list)
    waiting_on_others: list[TaskDTO] = field(default_factory=list)
