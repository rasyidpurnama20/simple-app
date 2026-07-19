import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from obe.shared.models import VersionedModel


class IntegrityIssue(VersionedModel):
    class Severity(models.TextChoices):
        BLOCKING = "blocking", "Blocking error"
        WARNING = "warning", "Review warning"
        INFORMATION = "information", "Information"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        ASSIGNED = "assigned", "Assigned"
        INVESTIGATING = "investigating", "Investigating"
        RESOLVED = "resolved", "Resolved"
        ACCEPTED_RISK = "accepted-risk", "Accepted risk"
        REOPENED = "reopened", "Reopened"
        VERIFIED = "verified", "Verified"

    severity = models.CharField(
        max_length=20,
        choices=Severity.choices,
    )
    reason_code = models.CharField(max_length=80, db_index=True)
    object_type = models.CharField(max_length=80)
    object_id = models.CharField(max_length=80)
    impact = models.TextField()
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    due_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.OPEN)
    evidence = models.JSONField(default=list)
    accepted_risk_reason = models.TextField(blank=True)
    source_snapshot = models.JSONField(default=dict, blank=True)
    source_checksum = models.CharField(max_length=64, blank=True)
    fingerprint = models.CharField(
        max_length=64, unique=True, null=True, blank=True, editable=False
    )
    resolution = models.TextField(blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="integrity_issues_verified",
    )

    def clean(self):
        super().clean()
        if self.status == self.Status.ACCEPTED_RISK and not self.accepted_risk_reason.strip():
            raise ValidationError("Accepted risk memerlukan alasan")
        if self.status == self.Status.VERIFIED and not self.verified_by_id:
            raise ValidationError("Verifikasi issue memerlukan verifier")

    @property
    def blocks_official_use(self) -> bool:
        return self.severity == self.Severity.BLOCKING and self.status != self.Status.VERIFIED


class IntegrityValidationRun(models.Model):
    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        PASSED = "passed", "Passed"
        BLOCKED = "blocked", "Blocked"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dataset_name = models.CharField(max_length=160)
    source_checksum = models.CharField(max_length=64, db_index=True)
    validator_version = models.CharField(max_length=40)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.RUNNING)
    statistics = models.JSONField(default=dict)
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["source_checksum", "validator_version"],
                name="integrity_run_checksum_version_unique",
            )
        ]


class QualityCycle(VersionedModel):
    period = models.CharField(max_length=40)
    scope_type = models.CharField(max_length=40)
    scope_id = models.CharField(max_length=80)
    standard = models.JSONField(default=dict)
    execution = models.JSONField(default=dict)
    evaluation = models.JSONField(default=dict)
    control = models.JSONField(default=dict)
    improvement = models.JSONField(default=dict)
    status = models.CharField(max_length=24, default="draft")
    approvals = models.JSONField(default=list)


class ImprovementAction(VersionedModel):
    issue = models.ForeignKey(IntegrityIssue, on_delete=models.PROTECT, related_name="actions")
    root_cause = models.TextField()
    action = models.TextField()
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    due_at = models.DateTimeField()
    success_indicator = models.TextField()
    status = models.CharField(max_length=24, default="planned")
    baseline = models.JSONField(default=dict)
    result = models.JSONField(default=dict)
    approval = models.JSONField(default=dict)
