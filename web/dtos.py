"""Presentation-facing DTOs for the Home landing page."""

from __future__ import annotations

from dataclasses import dataclass, field

from core.dtos import ActionDTO
from timeline.dtos import HomeGroupsDTO


@dataclass(frozen=True)
class WorkspaceLinkDTO:
    """A workspace entry shown in the Home navigation."""

    key: str
    label: str
    description: str
    available: bool


@dataclass(frozen=True)
class LandingDTO:
    """Everything the Home landing page needs to render."""

    role_label: str
    role: str
    prodi_name: str | None
    available_actions: list[ActionDTO] = field(default_factory=list)
    workspaces: list[WorkspaceLinkDTO] = field(default_factory=list)
    home_groups: HomeGroupsDTO = field(default_factory=HomeGroupsDTO)
