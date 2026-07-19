import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from obe.shared.models import VersionedModel


class AssessmentInstrument(VersionedModel):
    offering_public_id = models.UUIDField(db_index=True)
    code = models.CharField(max_length=24)
    title = models.CharField(max_length=200)
    kind = models.CharField(max_length=30)
    weight = models.DecimalField(max_digits=6, decimal_places=3)
    schedule = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=1)
    assessor_id = models.CharField(max_length=64)
    mappings = models.JSONField(default=list)
    rubric = models.JSONField(default=dict)
    evidence_required = models.BooleanField(default=True)
    status = models.CharField(max_length=20, default="draft")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["offering_public_id", "code", "version"],
                name="instrument_code_version_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(weight__gt=0) & models.Q(weight__lte=100),
                name="instrument_weight_range",
            ),
        ]


class Submission(VersionedModel):
    instrument = models.ForeignKey(
        AssessmentInstrument, on_delete=models.PROTECT, related_name="submissions"
    )
    student_id = models.CharField(max_length=64)
    attempt = models.PositiveSmallIntegerField(default=1)
    response = models.JSONField(default=dict)
    evidence_manifest_ids = models.JSONField(default=list)
    status = models.CharField(max_length=20, default="draft")
    submitted_at = models.DateTimeField(null=True, blank=True)
    receipt_checksum = models.CharField(max_length=64, blank=True)
    reopened_reason = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["instrument", "student_id", "attempt"], name="submission_attempt_unique"
            )
        ]


class Score(VersionedModel):
    submission = models.ForeignKey(Submission, on_delete=models.PROTECT, related_name="scores")
    raw_score = models.DecimalField(max_digits=9, decimal_places=3)
    max_score = models.DecimalField(max_digits=9, decimal_places=3)
    normalized = models.DecimalField(max_digits=6, decimal_places=2)
    letter = models.CharField(max_length=3, blank=True)
    grade_point = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    state = models.CharField(max_length=20, default="graded")
    rubric_trace = models.JSONField(default=dict)
    feedback = models.JSONField(default=dict)
    assessor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    published_at = models.DateTimeField(null=True, blank=True)
    change_reason = models.TextField(blank=True)

    def clean(self):
        if self.max_score <= 0:
            raise ValidationError("Max score harus lebih dari nol")
        if not Decimal("0") <= self.normalized <= Decimal("100"):
            raise ValidationError("Normalized score harus 0–100")


class AttainmentSnapshot(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scope_type = models.CharField(max_length=30)
    scope_id = models.CharField(max_length=80)
    outcome_code = models.CharField(max_length=24)
    actual = models.DecimalField(max_digits=6, decimal_places=2, null=True)
    target = models.DecimalField(max_digits=6, decimal_places=2)
    denominator = models.PositiveIntegerField()
    coverage = models.DecimalField(max_digits=6, decimal_places=2)
    formula_version = models.CharField(max_length=40)
    source_versions = models.JSONField(default=dict)
    trace = models.JSONField(default=list)
    blocking_reasons = models.JSONField(default=list)
    generated_at = models.DateTimeField(auto_now_add=True)
