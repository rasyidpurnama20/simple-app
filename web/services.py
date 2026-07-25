"""Presentation service layer for the Home landing page.

Business/orchestration logic for the landing page lives here so views stay
thin and call exactly one service method (Requirement 18.4).
"""

from __future__ import annotations

from core.dtos import RoleContextDTO
from core.services import RoleService
from timeline.services import HomeService

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
    def landing(
        role_context: RoleContextDTO | None, demo_user_id: int | None = None
    ) -> LandingDTO:
        """Assemble the landing DTO for the active role context.

        Includes the next-best-work grouping (Do Now / Next / Waiting on
        Others) for the active user, sourced from the Timeline_Engine's
        ``HomeService`` (Requirements 4.1-4.5).
        """
        workspaces = [
            WorkspaceLinkDTO(key=key, label=label, description=desc, available=avail)
            for (key, label, desc, avail) in _WORKSPACES
        ]

        resolved_user_id = demo_user_id
        if resolved_user_id is None and role_context is not None:
            resolved_user_id = role_context.demo_user_id
        home_groups = HomeService.next_best_work(resolved_user_id)

        if role_context is None:
            return LandingDTO(
                role_label="Tidak ada peran",
                role="",
                prodi_name=None,
                available_actions=[],
                workspaces=workspaces,
                home_groups=home_groups,
            )

        return LandingDTO(
            role_label=role_context.role_label,
            role=role_context.role,
            prodi_name=role_context.prodi_name,
            available_actions=role_context.available_actions,
            workspaces=workspaces,
            home_groups=home_groups,
        )

    @staticmethod
    def switch_role(demo_user_id: int) -> RoleContextDTO:
        """Delegate role switching to the core RoleService."""
        return RoleService.switch_role(demo_user_id)
