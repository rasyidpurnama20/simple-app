import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class VersionedModel(TimeStampedModel):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    version = models.PositiveIntegerField(default=1)
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    lock_version = models.PositiveIntegerField(default=0)

    class Meta:
        abstract = True


class AuditEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    occurred_at = models.DateTimeField(auto_now_add=True, db_index=True)
    actor_id = models.CharField(max_length=64, blank=True)
    actor_label = models.CharField(max_length=160, blank=True)
    actor_scope = models.CharField(max_length=160, blank=True)
    action = models.CharField(max_length=120, db_index=True)
    object_type = models.CharField(max_length=120, db_index=True)
    object_id = models.CharField(max_length=80, db_index=True)
    summary = models.CharField(max_length=255)
    before = models.JSONField(default=dict, blank=True)
    after = models.JSONField(default=dict, blank=True)
    reason = models.TextField(blank=True)
    correlation_id = models.UUIDField(default=uuid.uuid4, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    outcome = models.CharField(max_length=40, default="success")
    integrity_hash = models.CharField(max_length=64, blank=True)

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("AuditEvent bersifat append-only")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("AuditEvent tidak boleh dihapus")

    class Meta:
        ordering = ["-occurred_at"]
        indexes = [models.Index(fields=["object_type", "object_id", "occurred_at"])]


class OutboxEvent(models.Model):
    event_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_type = models.CharField(max_length=160, db_index=True)
    aggregate_id = models.CharField(max_length=80, db_index=True)
    aggregate_version = models.PositiveIntegerField(default=1)
    occurred_at = models.DateTimeField(auto_now_add=True)
    actor_id = models.CharField(max_length=64, blank=True)
    correlation_id = models.UUIDField(default=uuid.uuid4, db_index=True)
    payload_schema = models.CharField(max_length=40, default="1.0")
    payload = models.JSONField(default=dict)
    sensitivity = models.CharField(max_length=32, default="internal")
    published_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["occurred_at"]


class FeatureFlag(VersionedModel):
    class State(models.TextChoices):
        DISABLED = "disabled", "Disabled"
        INTERNAL = "internal", "Internal"
        PILOT = "pilot", "Pilot"
        GENERAL = "general", "General"
        DEPRECATED = "deprecated", "Deprecated"
        RETIRED = "retired", "Retired"

    code = models.SlugField(max_length=100)
    state = models.CharField(max_length=20, choices=State.choices, default=State.DISABLED)
    scope = models.JSONField(default=dict, blank=True)
    owner = models.CharField(max_length=160)
    acceptance_evidence = models.TextField(blank=True)
    rollback_plan = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["code", "version"], name="flag_version_unique")
        ]


class AcademicRule(VersionedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        REVIEWED = "reviewed", "Reviewed"
        ACTIVE = "active", "Active"
        RETIRED = "retired", "Retired"

    code = models.CharField(max_length=80)
    scope = models.JSONField(default=dict)
    input_schema = models.JSONField(default=dict)
    expression = models.JSONField(default=dict)
    priority = models.PositiveSmallIntegerField(default=100)
    severity = models.CharField(max_length=20, default="blocking")
    cohort = models.CharField(max_length=40, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="rules_created",
    )
    activated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="rules_activated",
    )

    def clean(self):
        if self.status == self.Status.ACTIVE and self.created_by_id == self.activated_by_id:
            raise ValidationError("Maker dan checker rule harus berbeda")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["code", "version"], name="rule_version_unique")
        ]


class FileManifest(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sha256 = models.CharField(max_length=64, db_index=True)
    size = models.PositiveBigIntegerField()
    mime_type = models.CharField(max_length=120)
    owner_id = models.CharField(max_length=64)
    academic_object = models.CharField(max_length=160)
    period = models.CharField(max_length=40, blank=True)
    version = models.PositiveIntegerField(default=1)
    classification = models.CharField(max_length=32, default="internal")
    content_path = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["sha256", "academic_object", "version"],
                name="manifest_object_version_unique",
            )
        ]
