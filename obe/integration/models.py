import uuid

from django.conf import settings
from django.db import models


class IntegrationBatch(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contract_code = models.CharField(max_length=80)
    schema_version = models.CharField(max_length=40)
    direction = models.CharField(max_length=8, choices=[("in", "Incoming"), ("out", "Outgoing")])
    source = models.CharField(max_length=80)
    idempotency_key = models.CharField(max_length=160, unique=True)
    checksum = models.CharField(max_length=64)
    record_count = models.PositiveIntegerField(default=0)
    state = models.CharField(max_length=24, default="staging")
    staging_payload = models.JSONField(default=list)
    validation_report = models.JSONField(default=dict)
    reconciliation = models.JSONField(default=dict)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    committed_at = models.DateTimeField(null=True, blank=True)
