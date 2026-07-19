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

    source_id = models.CharField(max_length=80, null=True, blank=True, unique=True)
    program_code = models.CharField(max_length=32)
    program_name = models.CharField(max_length=160, blank=True)
    degree_level = models.CharField(max_length=40, default="sarjana")
    name = models.CharField(max_length=160)
    curriculum_year = models.PositiveSmallIntegerField(null=True, blank=True)
    cohort_from = models.PositiveSmallIntegerField()
    cohort_to = models.PositiveSmallIntegerField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    checksum = models.CharField(max_length=64, blank=True)
    source_checksum = models.CharField(max_length=64, blank=True)
    approval_snapshot = models.JSONField(default=dict, blank=True)
    approval_documents = models.JSONField(default=list, blank=True)
    reviewed_by_actor_id = models.CharField(max_length=64, blank=True)
    approved_by_actor_id = models.CharField(max_length=64, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    archive_reason = models.TextField(blank=True)

    def clean(self):
        super().clean()
        if not self.program_code.strip() or not self.name.strip():
            raise ValidationError("Program dan nama versi kurikulum wajib diisi")
        if self.cohort_to is not None and self.cohort_to < self.cohort_from:
            raise ValidationError("Rentang cohort kurikulum tidak valid")
        if self.status == self.Status.ACTIVE:
            if not self.approved_by_actor_id or not self.approved_at or not self.activated_at:
                raise ValidationError("Kurikulum aktif memerlukan approval dan waktu aktivasi")
            if not self.checksum:
                raise ValidationError("Kurikulum aktif memerlukan checksum paket")

    def save(self, *args, **kwargs):
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).first()
            if previous and previous.status in {self.Status.ACTIVE, self.Status.ARCHIVED}:
                excluded = {"status", "archive_reason", "updated_at"}
                old = {
                    field.name: getattr(previous, field.name)
                    for field in self._meta.concrete_fields
                    if field.name not in excluded
                }
                new = {
                    field.name: getattr(self, field.name)
                    for field in self._meta.concrete_fields
                    if field.name not in excluded
                }
                if old != new or self.status not in {self.Status.ACTIVE, self.Status.ARCHIVED}:
                    raise ValidationError("Versi kurikulum aktif/arsip bersifat immutable")
                if self.status == self.Status.ARCHIVED and not self.archive_reason.strip():
                    raise ValidationError("Archive versi aktif memerlukan alasan")
        self.clean()
        return super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["program_code", "cohort_from", "version"],
                name="curriculum_program_cohort_version_unique",
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
    knowledge_depth = models.PositiveSmallIntegerField(null=True, blank=True)
    skill_depth = models.PositiveSmallIntegerField(null=True, blank=True)
    attitude_depth = models.PositiveSmallIntegerField(null=True, blank=True)
    owner_role = models.CharField(max_length=40, blank=True)
    weight = models.DecimalField(max_digits=7, decimal_places=4, default=0)
    target = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("75"))
    status = models.CharField(max_length=20, default="active")

    def clean(self):
        super().clean()
        if not self.code.strip() or not self.name.strip() or not self.description.strip():
            raise ValidationError("Outcome memerlukan code, nama, dan deskripsi")
        if self.kind == self.Kind.BK:
            if self.category.strip().lower() not in {"utama", "pendukung", "lainnya"}:
                raise ValidationError("Kategori bahan kajian tidak konsisten")
            if self.depth is None or not 1 <= self.depth <= 6:
                raise ValidationError("Bahan kajian memerlukan kategori dan depth 1–6")
            if not self.owner_role.strip() or self.weight <= 0:
                raise ValidationError("Bahan kajian memerlukan owner dan bobot")
            for value in (self.knowledge_depth, self.skill_depth, self.attitude_depth):
                if value is None or not 1 <= value <= 6:
                    raise ValidationError("Depth pengetahuan/keterampilan/sikap harus 1–6")

    def save(self, *args, **kwargs):
        if self.curriculum.status in {
            CurriculumVersion.Status.ACTIVE,
            CurriculumVersion.Status.ARCHIVED,
        }:
            raise ValidationError("Outcome pada kurikulum aktif/arsip bersifat immutable")
        self.clean()
        return super().save(*args, **kwargs)

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
    equivalence_codes = models.JSONField(default=list, blank=True)

    def clean(self):
        super().clean()
        if not self.code.strip() or not self.name.strip():
            raise ValidationError("Mata kuliah memerlukan code dan nama")
        if not 1 <= self.recommended_semester <= 8:
            raise ValidationError("Semester rekomendasi harus 1–8")
        if self.credits <= 0:
            raise ValidationError("SKS harus lebih dari nol")

    def save(self, *args, **kwargs):
        if self.curriculum.status in {
            CurriculumVersion.Status.ACTIVE,
            CurriculumVersion.Status.ARCHIVED,
        }:
            raise ValidationError("Mata kuliah pada kurikulum aktif/arsip bersifat immutable")
        self.clean()
        return super().save(*args, **kwargs)

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
    allocation_method = models.CharField(max_length=40, default="explicit")
    approval_reference = models.CharField(max_length=160, blank=True)
    is_unallocated = models.BooleanField(default=False)
    status = models.CharField(max_length=20, default="active")

    def clean(self):
        super().clean()
        if self.allocation_method == "equal-split":
            raise ValidationError("Equal split otomatis tidak diizinkan")
        if self.is_unallocated:
            if not Decimal("0") <= self.allocation_weight <= Decimal("100"):
                raise ValidationError("Sisa unallocated harus berada pada 0–100")
        elif not Decimal("0") < self.allocation_weight <= Decimal("100"):
            raise ValidationError("Allocation weight harus >0 dan ≤100")
        if self.source_type == self.target_type and self.source_id == self.target_id:
            raise ValidationError("Self-cycle tidak diizinkan")

    def save(self, *args, **kwargs):
        if self.curriculum.status in {
            CurriculumVersion.Status.ACTIVE,
            CurriculumVersion.Status.ARCHIVED,
        }:
            raise ValidationError("Mapping pada kurikulum aktif/arsip bersifat immutable")
        self.clean()
        return super().save(*args, **kwargs)

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
