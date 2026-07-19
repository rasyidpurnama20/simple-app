import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


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
    created_by_actor_id = models.CharField(max_length=64, blank=True)
    updated_by_actor_id = models.CharField(max_length=64, blank=True)

    def _validate_effective_period(self):
        if self.effective_to and (
            self.effective_from is None or self.effective_to < self.effective_from
        ):
            raise ValidationError("Periode efektif tidak valid")

    def clean(self):
        self._validate_effective_period()

    def save(self, *args, **kwargs):
        self._validate_effective_period()
        return super().save(*args, **kwargs)

    class Meta:
        abstract = True
        constraints = [
            models.CheckConstraint(
                condition=models.Q(version__gte=1),
                name="%(app_label)s_%(class)s_version_gte_1",
            ),
            models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True)
                | models.Q(
                    effective_from__isnull=False, effective_to__gte=models.F("effective_from")
                ),
                name="%(app_label)s_%(class)s_effective_period_valid",
            ),
        ]


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
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PUBLISHING = "publishing", "Publishing"
        PUBLISHED = "published", "Published"
        DEAD = "dead", "Dead"

    class Sensitivity(models.TextChoices):
        PUBLIC = "public", "Public"
        INTERNAL = "internal", "Internal"
        CONFIDENTIAL = "confidential", "Confidential"

    event_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_type = models.CharField(max_length=160, db_index=True)
    aggregate_id = models.CharField(max_length=80, db_index=True)
    aggregate_version = models.PositiveIntegerField(default=1)
    occurred_at = models.DateTimeField(auto_now_add=True)
    actor_id = models.CharField(max_length=64, blank=True)
    correlation_id = models.UUIDField(default=uuid.uuid4, db_index=True)
    payload_schema = models.CharField(max_length=40, default="1.0")
    payload = models.JSONField(default=dict)
    sensitivity = models.CharField(
        max_length=32,
        choices=Sensitivity.choices,
        default=Sensitivity.INTERNAL,
    )
    consumers = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    published_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField(default=timezone.now, db_index=True)
    locked_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=160, blank=True)

    class Meta:
        ordering = ["occurred_at"]
        indexes = [models.Index(fields=["status", "next_attempt_at", "occurred_at"])]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(aggregate_version__gte=1),
                name="outbox_aggregate_version_gte_1",
            ),
            models.CheckConstraint(
                condition=models.Q(attempts__lte=100),
                name="outbox_attempts_lte_100",
            ),
        ]


class InboxEvent(models.Model):
    class Status(models.TextChoices):
        PROCESSING = "processing", "Processing"
        PROCESSED = "processed", "Processed"
        REJECTED = "rejected", "Rejected"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_id = models.UUIDField()
    consumer = models.CharField(max_length=80)
    event_type = models.CharField(max_length=160)
    aggregate_id = models.CharField(max_length=80)
    aggregate_version = models.PositiveIntegerField()
    payload_schema = models.CharField(max_length=40)
    correlation_id = models.UUIDField(db_index=True)
    status = models.CharField(max_length=16, choices=Status.choices)
    detail = models.CharField(max_length=160, blank=True)
    result_hash = models.CharField(max_length=64, blank=True)
    processed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["consumer", "event_id"], name="inbox_consumer_event_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(aggregate_version__gte=1),
                name="inbox_aggregate_version_gte_1",
            ),
        ]
        indexes = [models.Index(fields=["consumer", "event_type", "aggregate_id"])]


class ConsumerCursor(models.Model):
    consumer = models.CharField(max_length=80)
    event_type = models.CharField(max_length=160)
    aggregate_id = models.CharField(max_length=80)
    last_version = models.PositiveIntegerField(default=0)
    last_event_id = models.UUIDField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["consumer", "event_type", "aggregate_id"],
                name="consumer_cursor_unique",
            )
        ]


class JobExecution(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task_name = models.CharField(max_length=180, db_index=True)
    queue = models.CharField(max_length=40, db_index=True)
    idempotency_key = models.CharField(max_length=160, unique=True)
    correlation_id = models.UUIDField(default=uuid.uuid4, db_index=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUEUED)
    payload_hash = models.CharField(max_length=64)
    result = models.JSONField(default=dict, blank=True)
    result_hash = models.CharField(max_length=64, blank=True)
    progress = models.PositiveSmallIntegerField(default=0)
    attempts = models.PositiveSmallIntegerField(default=0)
    generation = models.PositiveIntegerField(default=1)
    cancel_requested = models.BooleanField(default=False)
    lease_expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    expires_at = models.DateTimeField(db_index=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=160, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(progress__gte=0, progress__lte=100),
                name="job_progress_between_0_100",
            ),
            models.CheckConstraint(
                condition=models.Q(generation__gte=1),
                name="job_generation_gte_1",
            ),
        ]
        indexes = [models.Index(fields=["status", "lease_expires_at"])]


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
    class Classification(models.TextChoices):
        PUBLIC = "public", "Public"
        INTERNAL = "internal", "Internal"
        CONFIDENTIAL = "confidential", "Confidential"
        RESTRICTED_EXAM = "restricted-exam", "Restricted Exam"

    class ScanStatus(models.TextChoices):
        SKIPPED = "skipped", "Skipped"
        CLEAN = "clean", "Clean"
        INFECTED = "infected", "Infected"
        ERROR = "error", "Error"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sha256 = models.CharField(max_length=64, db_index=True)
    size = models.PositiveBigIntegerField()
    mime_type = models.CharField(max_length=120)
    owner_id = models.CharField(max_length=64)
    academic_object = models.CharField(max_length=160)
    period = models.CharField(max_length=40, blank=True)
    version = models.PositiveIntegerField(default=1)
    classification = models.CharField(
        max_length=32,
        choices=Classification.choices,
        default=Classification.INTERNAL,
    )
    original_filename = models.CharField(max_length=255, blank=True)
    content_path = models.CharField(max_length=255)
    scan_status = models.CharField(
        max_length=16,
        choices=ScanStatus.choices,
        default=ScanStatus.SKIPPED,
    )
    scanner_signature = models.CharField(max_length=160, blank=True)
    scanned_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("FileManifest bersifat immutable")
        if len(self.sha256) != 64 or any(
            character not in "0123456789abcdef" for character in self.sha256
        ):
            raise ValidationError("SHA-256 manifest tidak valid")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("FileManifest tidak boleh dihapus")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["academic_object", "version"],
                name="manifest_object_version_unique",
            ),
            models.CheckConstraint(condition=models.Q(size__gt=0), name="manifest_size_gt_0"),
            models.CheckConstraint(
                condition=models.Q(version__gte=1), name="manifest_version_gte_1"
            ),
        ]
        indexes = [models.Index(fields=["owner_id", "created_at"])]
