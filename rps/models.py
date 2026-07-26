"""RPS_Module models.

Implements RPS, CPMK, SubCPMK, SubCPMKIndicator, AssessmentInstrument, Rubric,
RubricCriterion, RubricLevel, and Score (Requirements 8.1, 8.3, 8.4, 9.1-9.4).
"""

from __future__ import annotations

from django.db import models

from core.models import ProductionReadinessModel


class RPSStatus(models.TextChoices):
    """RPS lifecycle states."""

    DRAFT = "draft", "Draft"
    SUBMITTED = "submitted", "Submitted"
    APPROVED = "approved", "Approved"


class RPS(ProductionReadinessModel):
    """Rencana Pembelajaran Semester - bound to one course/curriculum/class/period.

    Requirement 8.1: Each RPS is anchored to exactly one Course, Curriculum,
    class, and academic period.
    """

    course = models.ForeignKey(
        "curriculum.Course",
        on_delete=models.PROTECT,
        related_name="rps_plans",
    )
    curriculum = models.ForeignKey(
        "curriculum.Curriculum",
        on_delete=models.PROTECT,
        related_name="rps_plans",
    )
    class_name = models.CharField(max_length=64, blank=True)
    period = models.CharField(max_length=32, blank=True)

    class Meta:
        verbose_name = "RPS"
        verbose_name_plural = "RPS Plans"
        ordering = ["-created_time"]

    def __str__(self) -> str:
        return f"RPS: {self.course_id} ({self.period})"


class CPMK(models.Model):
    """Capaian Pembelajaran Mata Kuliah - course-level learning outcome.

    Each CPMK derives from one or more CPLs of the RPS's bound curriculum
    (M2M derived_from, Requirement 8.2, 8.5).
    """

    rps = models.ForeignKey(
        RPS,
        on_delete=models.CASCADE,
        related_name="cpmks",
    )
    code = models.CharField(max_length=32)
    description = models.TextField(blank=True)
    derived_from = models.ManyToManyField(
        "curriculum.CPL",
        related_name="derived_cpmks",
        blank=True,
    )

    class Meta:
        verbose_name = "CPMK"
        verbose_name_plural = "CPMKs"
        ordering = ["code"]

    def __str__(self) -> str:
        return self.code


class SubCPMK(models.Model):
    """A sub-component of a CPMK."""

    cpmk = models.ForeignKey(
        CPMK,
        on_delete=models.CASCADE,
        related_name="sub_cpmks",
    )
    code = models.CharField(max_length=32)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name = "Sub-CPMK"
        verbose_name_plural = "Sub-CPMKs"
        ordering = ["code"]

    def __str__(self) -> str:
        return self.code


class SubCPMKIndicator(models.Model):
    """A measurable indicator for a Sub-CPMK."""

    sub_cpmk = models.ForeignKey(
        SubCPMK,
        on_delete=models.CASCADE,
        related_name="indicators",
    )
    code = models.CharField(max_length=32)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name = "Sub-CPMK Indicator"
        verbose_name_plural = "Sub-CPMK Indicators"
        ordering = ["code"]

    def __str__(self) -> str:
        return self.code


class AssessmentInstrument(ProductionReadinessModel):
    """An assessment instrument associated with an RPS."""

    rps = models.ForeignKey(
        RPS,
        on_delete=models.CASCADE,
        related_name="instruments",
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name = "Assessment Instrument"
        verbose_name_plural = "Assessment Instruments"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Rubric(ProductionReadinessModel):
    """A rubric belonging to an assessment instrument (1:1, Requirement 9.1)."""

    instrument = models.OneToOneField(
        AssessmentInstrument,
        on_delete=models.CASCADE,
        related_name="rubric",
    )
    name = models.CharField(max_length=255)

    class Meta:
        verbose_name = "Rubric"
        verbose_name_plural = "Rubrics"

    def __str__(self) -> str:
        return self.name


class RubricCriterion(models.Model):
    """A criterion in a rubric with a weight and mapped indicators.

    Weight is stored as an integer percentage (e.g. 25 means 25%).
    mapped_indicators is M2M to SubCPMKIndicator (Requirement 9.3).
    """

    rubric = models.ForeignKey(
        Rubric,
        on_delete=models.CASCADE,
        related_name="criteria",
    )
    name = models.CharField(max_length=255)
    weight = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    order = models.PositiveIntegerField(default=0)
    mapped_indicators = models.ManyToManyField(
        SubCPMKIndicator,
        related_name="mapped_criteria",
        blank=True,
    )

    class Meta:
        verbose_name = "Rubric Criterion"
        verbose_name_plural = "Rubric Criteria"
        ordering = ["order", "id"]

    def __str__(self) -> str:
        return self.name


class RubricLevel(models.Model):
    """A performance level for a rubric criterion (label + score)."""

    criterion = models.ForeignKey(
        RubricCriterion,
        on_delete=models.CASCADE,
        related_name="levels",
    )
    label = models.CharField(max_length=64)
    score = models.DecimalField(max_digits=5, decimal_places=2)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Rubric Level"
        verbose_name_plural = "Rubric Levels"
        ordering = ["order", "id"]

    def __str__(self) -> str:
        return f"{self.label} ({self.score})"


class Score(models.Model):
    """A graded score for a rubric criterion (per subject/student-proxy)."""

    criterion = models.ForeignKey(
        RubricCriterion,
        on_delete=models.CASCADE,
        related_name="scores",
    )
    student_proxy = models.CharField(max_length=64, blank=True)
    value = models.DecimalField(max_digits=6, decimal_places=2)
    created_time = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Score"
        verbose_name_plural = "Scores"
        ordering = ["-created_time"]

    def __str__(self) -> str:
        return f"Score {self.value} for {self.criterion_id}"
