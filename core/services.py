"""Core service layer: Role_Switcher context and versioned configuration.

All business logic lives here; views call these methods and never touch the
ORM directly (Requirement 18.4). Cross-cutting concerns (the active demo role,
versioned config) are exposed as transport-agnostic service methods returning
DTOs.
"""

from __future__ import annotations

from django.db import transaction

from .dtos import (
    ActionDTO,
    ConfigRecordDTO,
    RoleContextDTO,
    RoleOptionDTO,
)
from .exceptions import DomainError
from .models import ConfigRecord, DemoUser, Role

# Session key under which the active demo user id is stored. Isolating this in
# one place means real authentication can replace the mechanism later without
# touching callers (Requirement 15.4).
ACTIVE_DEMO_USER_SESSION_KEY = "active_demo_user_id"


# The actions each role can take, keyed by role. This drives the UI so that
# switching role changes the available actions (Requirement 15.2).
_ROLE_ACTIONS: dict[str, list[ActionDTO]] = {
    Role.KAPRODI: [
        ActionDTO("Buka OBE Cycle dari template", "timeline",
                  "Mulai siklus OBE baru dari template linimasa."),
        ActionDTO("Lihat linimasa & ketergantungan", "timeline",
                  "Pantau fase, milestone, dan tugas."),
        ActionDTO("Jalankan perhitungan ketercapaian", "attainment",
                  "Hitung ketercapaian capaian pembelajaran."),
    ],
    Role.LECTURER: [
        ActionDTO("Susun kurikulum & CPL", "curriculum",
                  "Kelola kurikulum, CPL, indikator, dan mata kuliah."),
        ActionDTO("Tulis RPS & rubrik", "learning",
                  "Susun RPS, CPMK, instrumen penilaian, dan rubrik."),
    ],
    Role.DEV_ADMIN: [
        ActionDTO("Muat data sintetis", "home",
                  "Muat atau reset data demo."),
    ],
}


class RoleService:
    """Manages the in-app active role (no authentication, Req 15.2/15.4)."""

    @staticmethod
    def available_roles() -> list[RoleOptionDTO]:
        """All demo users that can be assumed via the Role_Switcher."""
        return [
            RoleOptionDTO(
                demo_user_id=user.id,
                name=user.name,
                role=user.role,
                role_label=user.get_role_display(),
            )
            for user in DemoUser.objects.all()
        ]

    @staticmethod
    def actions_for_role(role: str) -> list[ActionDTO]:
        """The actions available to a given role (drives the UI, Req 15.2)."""
        return list(_ROLE_ACTIONS.get(role, []))

    @classmethod
    def active_context(cls, demo_user_id: int | None) -> RoleContextDTO | None:
        """Build the active-role context for the given demo user id.

        Returns ``None`` when there is no resolvable active user.
        """
        user = cls._resolve_user(demo_user_id)
        if user is None:
            return None
        return RoleContextDTO(
            demo_user_id=user.id,
            name=user.name,
            role=user.role,
            role_label=user.get_role_display(),
            prodi_name=user.prodi.name if user.prodi_id else None,
            available_actions=cls.actions_for_role(user.role),
        )

    @classmethod
    def default_user_id(cls) -> int | None:
        """The demo user selected by default when no role is chosen yet."""
        user = (
            DemoUser.objects.filter(role=Role.KAPRODI).first()
            or DemoUser.objects.first()
        )
        return user.id if user else None

    @staticmethod
    def _resolve_user(demo_user_id: int | None) -> DemoUser | None:
        if not demo_user_id:
            return None
        return DemoUser.objects.filter(pk=demo_user_id).first()

    @classmethod
    def switch_role(cls, demo_user_id: int) -> RoleContextDTO:
        """Validate and return the context for switching to ``demo_user_id``.

        Raises a plain-language ``DomainError`` if the user does not exist.
        """
        context = cls.active_context(demo_user_id)
        if context is None:
            raise DomainError(
                message="Peran yang dipilih tidak ditemukan.",
                corrective_step="Pilih salah satu peran demo yang tersedia "
                "dari daftar.",
            )
        return context


class ConfigService:
    """Versioned configuration records (Requirement 18.2)."""

    @staticmethod
    @transaction.atomic
    def set_config(key: str, definition: dict, category: str = ConfigRecord.Category.RULE) -> ConfigRecordDTO:
        """Store a new active version of ``key``, deactivating older versions.

        Versions are monotonic per key so calculations remain reproducible and
        auditable.
        """
        latest = (
            ConfigRecord.objects.select_for_update()
            .filter(key=key)
            .order_by("-version")
            .first()
        )
        next_version = (latest.version + 1) if latest else 1
        ConfigRecord.objects.filter(key=key, is_active=True).update(is_active=False)
        record = ConfigRecord.objects.create(
            key=key,
            category=category,
            version=next_version,
            definition=definition,
            is_active=True,
        )
        return ConfigService._to_dto(record)

    @staticmethod
    def get_active(key: str) -> ConfigRecordDTO | None:
        """Return the currently active version of ``key`` (or ``None``)."""
        record = ConfigRecord.objects.filter(key=key, is_active=True).first()
        return ConfigService._to_dto(record) if record else None

    @staticmethod
    def history(key: str) -> list[ConfigRecordDTO]:
        """All versions of ``key`` newest-first."""
        return [
            ConfigService._to_dto(record)
            for record in ConfigRecord.objects.filter(key=key).order_by("-version")
        ]

    @staticmethod
    def _to_dto(record: ConfigRecord) -> ConfigRecordDTO:
        return ConfigRecordDTO(
            key=record.key,
            category=record.category,
            version=record.version,
            definition=record.definition,
            is_active=record.is_active,
        )
