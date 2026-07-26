"""Excel Import models: ImportBatch, StagedRow, TemplateDefinition.

Requirements: 7.1, 7.2, 1.3, 1.4, 1.6, 5.4, 6.3, 9.1.
"""

from __future__ import annotations

import uuid

from django.db import models

from core.models import ProductionReadinessModel


class ImportStatus(models.TextChoices):
    """Import batch lifecycle states (Requirement 7.2)."""

    DIUNGGAH = "Diunggah", "Diunggah"
    DIVALIDASI = "Divalidasi", "Divalidasi"
    DITOLAK = "Ditolak", "Ditolak"
    DIKOMIT = "Dikomit", "Dikomit"
    DIGAGALKAN = "Digagalkan", "Digagalkan"


class RowClassification(models.TextChoices):
    """Row classification after dry-run (Requirement 5.3)."""

    NEW = "New_Row", "New Row"
    CHANGED = "Changed_Row", "Changed Row"
    UNCHANGED = "Unchanged_Row", "Unchanged Row"
    DUPLICATE = "Duplicate_Row", "Duplicate Row"
    REJECTED = "Rejected_Row", "Rejected Row"


class ImportBatch(ProductionReadinessModel):
    """An import batch carrying identity, scope, type, and version.

    Reuses ProductionReadinessModel for production-readiness fields.
    Requirements: 7.1, 7.2.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template_type = models.CharField(max_length=40)
    schema_version = models.CharField(max_length=20)
    # Import_Scope
    import_prodi = models.CharField(max_length=64, blank=True)
    period = models.CharField(max_length=32, blank=True)
    klass = models.CharField(max_length=64, blank=True)
    timeline_task_id = models.CharField(max_length=64, null=True, blank=True)
    batch_status = models.CharField(
        max_length=12,
        choices=ImportStatus.choices,
        default=ImportStatus.DIUNGGAH,
    )
    content_hash = models.CharField(max_length=64, blank=True)

    class Meta:
        verbose_name = "Import Batch"
        verbose_name_plural = "Import Batches"
        ordering = ["-created_time"]

    def __str__(self) -> str:
        return f"Batch {self.id} ({self.template_type} {self.batch_status})"


class StagedRow(models.Model):
    """A staged row from an uploaded Data sheet.

    Requirements: 5.1, 5.3, 5.4.
    """

    batch = models.ForeignKey(
        ImportBatch,
        on_delete=models.CASCADE,
        related_name="rows",
    )
    row_index = models.PositiveIntegerField()
    raw_values = models.JSONField(default=dict)
    business_key = models.CharField(max_length=255, db_index=True)
    classification = models.CharField(
        max_length=16,
        choices=RowClassification.choices,
        null=True,
        blank=True,
    )
    cell_errors = models.JSONField(default=list)

    class Meta:
        verbose_name = "Staged Row"
        verbose_name_plural = "Staged Rows"
        unique_together = ("batch", "row_index")
        ordering = ["row_index"]

    def __str__(self) -> str:
        return f"Row {self.row_index} ({self.classification})"


class TemplateDefinition(models.Model):
    """A versioned template definition (append-only).

    Requirements: 1.3, 1.4, 1.5, 1.6.
    """

    template_type = models.CharField(max_length=40)
    schema_version = models.CharField(max_length=20)
    is_implemented = models.BooleanField(default=False)
    fields = models.JSONField(default=list)
    reference_sources = models.JSONField(default=list)
    validation_rules = models.JSONField(default=list)
    business_key = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Template Definition"
        verbose_name_plural = "Template Definitions"
        unique_together = ("template_type", "schema_version")
        ordering = ["template_type", "-created_at"]

    def __str__(self) -> str:
        return f"{self.template_type} v{self.schema_version}"
