"""Result DTOs for the core module.

DTOs are the transport-agnostic return type of service methods. Views (and a
future JSON API) consume these instead of ORM models, keeping the service
layer independent of the presentation layer (Requirement 18.4).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ActionDTO:
    """A single action available to a role in the UI."""

    label: str
    workspace: str
    description: str = ""


@dataclass(frozen=True)
class RoleContextDTO:
    """The active-role context surfaced to templates by the Role_Switcher."""

    demo_user_id: int | None
    name: str
    role: str
    role_label: str
    prodi_name: str | None
    available_actions: list[ActionDTO] = field(default_factory=list)


@dataclass(frozen=True)
class RoleOptionDTO:
    """A selectable option in the "Lihat sebagai <role>" switcher."""

    demo_user_id: int
    name: str
    role: str
    role_label: str


@dataclass(frozen=True)
class ConfigRecordDTO:
    """A versioned configuration record."""

    key: str
    category: str
    version: int
    definition: dict
    is_active: bool
