"""Curriculum_Module models.

Implements Curriculum, CPL, CPLIndicator, Course, and CourseCPLContribution.
All business entities extend ProductionReadinessModel for production-readiness
fields (Requirements 6.1, 6.2, 6.3, 6.6, 7.2, 7.3).
"""

from __future__ import annotations

from django.db import models

from core.models import ProductionReadinessModel


class CurriculumStatus(models.TextChoices):
    """Curriculum lifecycle states (Requirement 6.6)."""

    DRAFT = "draft", "Draft"
    ACTIVE = "active", "Active"
    ARCHIVED = "archived", "Archived"


class ContributionLevel(models.TextChoices):
    """Course-to-CPL contribution levels (Requirements 7.1, 7.4)."""

    INTRODUCE = "Introduce", "Introduce"
    REINFORCE = "Reinforce", "Reinforce"
    MASTER = "Master", "Master"


class Curriculum(ProductionReadinessModel):
    """A curriculum for a program of study.

    At most one curriculum per prodi may be active at any time, enforced by
    the service layer and a partial unique index (Requirements 6.4, 6.5).
    """

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    year = models.CharField(max_length=32, blank=True)

    class Meta:
        verbose_name = "Curriculum"
        verbose_name_plural = "Curricula"
        ordering = ["-created_time"]
        constraints = [
            models.UniqueConstraint(
                fields=["prodi"],
                condition=models.Q(status="active"),
                name="uniq_active_curriculum_per_prodi",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class CPL(ProductionReadinessModel):
    """A Capaian Pembelajaran Lulusan (graduate learning outcome).

    Belongs to a curriculum. Each CPL may have multiple CPLIndicators.
    """

    curriculum = models.ForeignKey(
        Curriculum,
        on_delete=models.CASCADE,
        related_name="cpls",
    )
    code = models.CharField(max_length=32)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name = "CPL"
        verbose_name_plural = "CPLs"
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(
                fields=["curriculum", "code"],
                name="uniq_cpl_code_per_curriculum",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.code}"


class CPLIndicator(models.Model):
    """A measurable indicator for a CPL with a numeric target value."""

    cpl = models.ForeignKey(
        CPL,
        on_delete=models.CASCADE,
        related_name="indicators",
    )
    code = models.CharField(max_length=32)
    description = models.TextField(blank=True)
    target_value = models.DecimalField(max_digits=6, decimal_places=2, default=70.00)

    class Meta:
        verbose_name = "CPL Indicator"
        verbose_name_plural = "CPL Indicators"
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(
                fields=["cpl", "code"],
                name="uniq_cplindicator_code_per_cpl",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.code}"


class Course(ProductionReadinessModel):
    """A course belonging to a curriculum."""

    curriculum = models.ForeignKey(
        Curriculum,
        on_delete=models.CASCADE,
        related_name="courses",
    )
    code = models.CharField(max_length=32)
    name = models.CharField(max_length=255)
    credits = models.PositiveIntegerField(default=3)

    class Meta:
        verbose_name = "Course"
        verbose_name_plural = "Courses"
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(
                fields=["curriculum", "code"],
                name="uniq_course_code_per_curriculum",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class CourseCPLContribution(models.Model):
    """Maps a Course to a CPL with a contribution level (M2M through model).

    Supports many-to-many in both directions: a course can contribute to
    multiple CPLs and a CPL can be contributed to by multiple courses
    (Requirements 7.2, 7.3).
    """

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="cpl_contributions",
    )
    cpl = models.ForeignKey(
        CPL,
        on_delete=models.CASCADE,
        related_name="course_contributions",
    )
    contribution_level = models.CharField(
        max_length=16,
        choices=ContributionLevel.choices,
    )

    class Meta:
        verbose_name = "Course CPL Contribution"
        verbose_name_plural = "Course CPL Contributions"
        constraints = [
            models.UniqueConstraint(
                fields=["course", "cpl"],
                name="uniq_course_cpl_contribution",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.course_id} -> {self.cpl_id} ({self.contribution_level})"
