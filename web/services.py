"""Presentation service layer for the Home landing page.

Business/orchestration logic for the landing page lives here so views stay
thin and call exactly one service method (Requirement 18.4).
"""

from __future__ import annotations

from core.dtos import RoleContextDTO
from core.services import RoleService

from .dtos import LandingDTO, WorkspaceLinkDTO

# The five fixed workspaces (Requirement 16.1). "available" marks which are
# wired up so far; only Home is functional in Task 1.
_WORKSPACES = [
    ("home", "Home", "Pekerjaan berikutnya: Do Now / Next / Waiting on Others.", True),
    ("timeline", "Timeline", "Siklus OBE, template, fase, milestone, tugas.", False),
    ("curriculum", "Curriculum", "Kurikulum, CPL, indikator, mata kuliah.", False),
    ("learning", "Learning", "Penyusunan RPS, CPMK, instrumen, rubrik.", False),
    ("attainment", "Attainment & Quality", "Hitung ketercapaian & tugas tindak lanjut.", False),
]


class LandingService:
    """Builds the Home landing-page view model."""

    @staticmethod
    def landing(role_context: RoleContextDTO | None) -> LandingDTO:
        """Assemble the landing DTO for the active role context."""
        workspaces = [
            WorkspaceLinkDTO(key=key, label=label, description=desc, available=avail)
            for (key, label, desc, avail) in _WORKSPACES
        ]

        if role_context is None:
            return LandingDTO(
                role_label="Tidak ada peran",
                role="",
                prodi_name=None,
                available_actions=[],
                workspaces=workspaces,
            )

        return LandingDTO(
            role_label=role_context.role_label,
            role=role_context.role,
            prodi_name=role_context.prodi_name,
            available_actions=role_context.available_actions,
            workspaces=workspaces,
        )

    @staticmethod
    def switch_role(demo_user_id: int) -> RoleContextDTO:
        """Delegate role switching to the core RoleService."""
        return RoleService.switch_role(demo_user_id)
