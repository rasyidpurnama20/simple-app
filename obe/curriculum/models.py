from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models

from obe.shared.models import VersionedModel


class CurriculumVersion(VersionedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        REVIEW = "review", "Review"
        ACTIVE = "active", "Active"
        ARCHIVED = "archived", "Archived"

    program_code = models.CharField(max_length=32)
    name = models.CharField(max_length=160)
    cohort_from = models.PositiveSmallIntegerField()
    cohort_to = models.PositiveSmallIntegerField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    checksum = models.CharField(max_length=64, blank=True)
    approval_snapshot = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["program_code", "version"], name="curriculum_program_version_unique"
            )
        ]


class Outcome(VersionedModel):
    class Kind(models.TextChoices):
        PL = "PL", "Profil Lulusan"
        CPL = "CPL", "CPL"
        BK = "BK", "Bahan Kajian"
        CPMK = "CPMK", "CPMK Program"

    curriculum = models.ForeignKey(
        CurriculumVersion, on_delete=models.PROTECT, related_name="outcomes"
    )
    kind = models.CharField(max_length=8, choices=Kind.choices)
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=200)
    description = models.TextField()
    category = models.CharField(max_length=80, blank=True)
    depth = models.PositiveSmallIntegerField(null=True, blank=True)
    weight = models.DecimalField(max_digits=7, decimal_places=4, default=0)
    target = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("75"))
    status = models.CharField(max_length=20, default="active")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["curriculum", "kind", "code", "version"],
                name="outcome_code_version_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(weight__gte=0) & models.Q(weight__lte=100),
                name="outcome_weight_range",
            ),
        ]


class Course(VersionedModel):
    curriculum = models.ForeignKey(
        CurriculumVersion, on_delete=models.PROTECT, related_name="courses"
    )
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=200)
    credits = models.PositiveSmallIntegerField()
    required = models.BooleanField(default=True)
    recommended_semester = models.PositiveSmallIntegerField()
    term = models.CharField(
        max_length=10, choices=[("odd", "Ganjil"), ("even", "Genap"), ("both", "Keduanya")]
    )
    prerequisites = models.JSONField(default=list, blank=True)
    capacity = models.PositiveIntegerField(default=40)
    status = models.CharField(max_length=20, default="active")

    def clean(self):
        if not 1 <= self.recommended_semester <= 8:
            raise ValidationError("Semester rekomendasi harus 1–8")
        if self.credits <= 0:
            raise ValidationError("SKS harus lebih dari nol")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["curriculum", "code", "version"], name="course_code_version_unique"
            )
        ]


class CurriculumEdge(VersionedModel):
    curriculum = models.ForeignKey(
        CurriculumVersion, on_delete=models.PROTECT, related_name="edges"
    )
    source_type = models.CharField(max_length=20)
    source_id = models.CharField(max_length=80)
    target_type = models.CharField(max_length=20)
    target_id = models.CharField(max_length=80)
    allocation_weight = models.DecimalField(max_digits=7, decimal_places=4)
    status = models.CharField(max_length=20, default="active")

    def clean(self):
        if not Decimal("0") < self.allocation_weight <= Decimal("100"):
            raise ValidationError("Allocation weight harus >0 dan ≤100")
        if self.source_type == self.target_type and self.source_id == self.target_id:
            raise ValidationError("Self-cycle tidak diizinkan")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "curriculum",
                    "source_type",
                    "source_id",
                    "target_type",
                    "target_id",
                    "version",
                ],
                name="curriculum_edge_unique",
            )
        ]
