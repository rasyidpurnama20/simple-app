from django.conf import settings
from django.db import models

from obe.shared.models import VersionedModel


class IntegrityIssue(VersionedModel):
    severity = models.CharField(
        max_length=20,
        choices=[("blocking", "Blocking"), ("warning", "Warning"), ("information", "Information")],
    )
    reason_code = models.CharField(max_length=80, db_index=True)
    object_type = models.CharField(max_length=80)
    object_id = models.CharField(max_length=80)
    impact = models.TextField()
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    due_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=24, default="open")
    evidence = models.JSONField(default=list)
    accepted_risk_reason = models.TextField(blank=True)


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
