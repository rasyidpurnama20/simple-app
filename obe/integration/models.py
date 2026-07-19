import uuid

from django.conf import settings
from django.db import models

from obe.shared.models import VersionedModel


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


class IdentifierAlias(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    namespace = models.CharField(
        max_length=32,
        choices=[("course-code", "Course code"), ("course-offering", "Course offering")],
    )
    legacy_identifier = models.CharField(max_length=120)
    canonical_identifier = models.CharField(max_length=120)
    status = models.CharField(max_length=24, default="resolved")
    source_checksum = models.CharField(max_length=64, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["namespace", "legacy_identifier"], name="identifier_alias_unique"
            )
        ]
        indexes = [models.Index(fields=["namespace", "canonical_identifier"])]


class IntegrationContract(VersionedModel):
    source_id = models.CharField(max_length=120, unique=True)
    system = models.CharField(max_length=80)
    direction = models.CharField(max_length=32)
    mode = models.CharField(max_length=80)
    schema_version = models.CharField(max_length=40)
    status = models.CharField(max_length=32)
    write_feature_flag = models.CharField(max_length=120, blank=True)
    source_snapshot = models.JSONField(default=dict)
