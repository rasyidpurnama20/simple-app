"""Curriculum_Module service layer.

All curriculum business logic lives here: create_curriculum, activate_curriculum,
map_course_to_cpl. Views and cross-module callers use these methods only.
"""

from __future__ import annotations

from django.db import transaction

from core.exceptions import DomainError
from core.models import DemoUser

from .models import (
    ContributionLevel,
    CourseCPLContribution,
    CPL,
    CPLIndicator,
    Course,
    Curriculum,
    CurriculumStatus,
)


class CurriculumService:
    """Business logic for the Curriculum_Module."""

    # -- Curriculum lifecycle (Requirements 6.1-6.6) ----------------------

    @staticmethod
    @transaction.atomic
    def create_curriculum(data: dict, actor) -> Curriculum:
        """Create a new curriculum in draft status.

        Requirements: 6.1, 6.2, 6.3.
        """
        actor_obj = _resolve_actor(actor)
        prodi = data.get("prodi") or (actor_obj.prodi if actor_obj else None)
        if prodi is None:
            raise DomainError(
                "Tidak dapat membuat kurikulum tanpa program studi.",
                "Pilih program studi terlebih dahulu.",
            )

        curriculum = Curriculum.objects.create(
            name=data.get("name", "Kurikulum Baru"),
            description=data.get("description", ""),
            year=data.get("year", ""),
            prodi=prodi,
            owner=actor_obj,
            creator=actor_obj,
            status=CurriculumStatus.DRAFT,
        )
        return curriculum

    @staticmethod
    @transaction.atomic
    def activate_curriculum(curriculum_id, actor) -> Curriculum:
        """Activate a curriculum, enforcing single-active-per-prodi.

        At most one curriculum per prodi may be active. If another is already
        active, raise DomainError naming the existing active curriculum and
        the corrective step (Requirements 6.4, 6.5).
        """
        curriculum = Curriculum.objects.get(pk=curriculum_id)

        # Lifecycle enforcement (Requirement 6.6)
        if curriculum.status == CurriculumStatus.ARCHIVED:
            raise DomainError(
                "Kurikulum yang sudah diarsipkan tidak dapat diaktifkan kembali.",
                "Buat kurikulum baru sebagai pengganti.",
            )
        if curriculum.status == CurriculumStatus.ACTIVE:
            raise DomainError(
                "Kurikulum ini sudah dalam status aktif.",
                "Tidak diperlukan tindakan lebih lanjut.",
            )

        # Single-active enforcement (Requirements 6.4, 6.5)
        existing_active = Curriculum.objects.filter(
            prodi=curriculum.prodi,
            status=CurriculumStatus.ACTIVE,
        ).exclude(pk=curriculum_id).first()

        if existing_active:
            raise DomainError(
                f"Program studi ini sudah memiliki kurikulum aktif: "
                f"\"{existing_active.name}\".",
                "Arsipkan kurikulum aktif yang ada terlebih dahulu, "
                "kemudian aktifkan kurikulum ini.",
            )

        curriculum.status = CurriculumStatus.ACTIVE
        curriculum.save(update_fields=["status", "modified_time"])
        return curriculum

    @staticmethod
    @transaction.atomic
    def archive_curriculum(curriculum_id, actor) -> Curriculum:
        """Archive a curriculum (only active curricula can be archived)."""
        curriculum = Curriculum.objects.get(pk=curriculum_id)
        if curriculum.status != CurriculumStatus.ACTIVE:
            raise DomainError(
                "Hanya kurikulum aktif yang dapat diarsipkan.",
                "Aktifkan kurikulum ini terlebih dahulu jika ingin mengarsipkannya.",
            )
        curriculum.status = CurriculumStatus.ARCHIVED
        curriculum.save(update_fields=["status", "modified_time"])
        return curriculum

    # -- CPL management ---------------------------------------------------

    @staticmethod
    @transaction.atomic
    def add_cpl(curriculum_id, data: dict, actor) -> CPL:
        """Add a CPL to a curriculum."""
        actor_obj = _resolve_actor(actor)
        curriculum = Curriculum.objects.get(pk=curriculum_id)
        cpl = CPL.objects.create(
            curriculum=curriculum,
            code=data.get("code", ""),
            description=data.get("description", ""),
            prodi=curriculum.prodi,
            owner=actor_obj,
            creator=actor_obj,
            status=curriculum.status,
        )
        return cpl

    @staticmethod
    @transaction.atomic
    def add_cpl_indicator(cpl_id, data: dict, actor) -> CPLIndicator:
        """Add an indicator to a CPL."""
        cpl = CPL.objects.get(pk=cpl_id)
        indicator = CPLIndicator.objects.create(
            cpl=cpl,
            code=data.get("code", ""),
            description=data.get("description", ""),
            target_value=data.get("target_value", 70.00),
        )
        return indicator

    # -- Course management ------------------------------------------------

    @staticmethod
    @transaction.atomic
    def add_course(curriculum_id, data: dict, actor) -> Course:
        """Add a course to a curriculum."""
        actor_obj = _resolve_actor(actor)
        curriculum = Curriculum.objects.get(pk=curriculum_id)
        course = Course.objects.create(
            curriculum=curriculum,
            code=data.get("code", ""),
            name=data.get("name", ""),
            credits=data.get("credits", 3),
            prodi=curriculum.prodi,
            owner=actor_obj,
            creator=actor_obj,
            status=curriculum.status,
        )
        return course

    # -- Course -> CPL contribution mapping (Requirements 7.1-7.4) -------

    @staticmethod
    @transaction.atomic
    def map_course_to_cpl(course_id, cpl_id, level: str, actor) -> CourseCPLContribution:
        """Map a course to a CPL with a contribution level.

        Requires level in {Introduce, Reinforce, Master}. Rejects any other
        value with the allowed values listed (Requirements 7.1, 7.4).
        """
        valid_levels = [c.value for c in ContributionLevel]
        if level not in valid_levels:
            raise DomainError(
                f"Tingkat kontribusi \"{level}\" tidak valid.",
                f"Gunakan salah satu dari: {', '.join(valid_levels)}.",
            )

        course = Course.objects.get(pk=course_id)
        cpl = CPL.objects.get(pk=cpl_id)

        contribution, _ = CourseCPLContribution.objects.update_or_create(
            course=course,
            cpl=cpl,
            defaults={"contribution_level": level},
        )
        return contribution

    # -- Read helpers for cross-module use --------------------------------

    @staticmethod
    def get_curriculum(curriculum_id) -> Curriculum:
        """Get a curriculum by ID."""
        return Curriculum.objects.get(pk=curriculum_id)

    @staticmethod
    def get_active_curriculum(prodi) -> Curriculum | None:
        """Get the active curriculum for a prodi (or None)."""
        return Curriculum.objects.filter(
            prodi=prodi, status=CurriculumStatus.ACTIVE
        ).first()

    @staticmethod
    def get_cpls(curriculum_id) -> list[CPL]:
        """Get all CPLs for a curriculum."""
        return list(CPL.objects.filter(curriculum_id=curriculum_id).prefetch_related("indicators"))

    @staticmethod
    def get_cpl(cpl_id) -> CPL:
        """Get a single CPL by ID."""
        return CPL.objects.get(pk=cpl_id)

    @staticmethod
    def get_courses(curriculum_id) -> list[Course]:
        """Get all courses for a curriculum."""
        return list(Course.objects.filter(curriculum_id=curriculum_id))

    @staticmethod
    def list_editable(scope, template_type=None):
        """Return editable records for Excel import prefill."""
        return []


def _resolve_actor(actor) -> DemoUser | None:
    """Accept a DemoUser instance or an id and return the DemoUser (or None)."""
    if actor is None:
        return None
    if isinstance(actor, DemoUser):
        return actor
    return DemoUser.objects.filter(pk=actor).first()
