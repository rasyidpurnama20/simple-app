import hashlib
import json
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


class AppendOnlyAuditQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("AuditEvent bersifat append-only")

    def delete(self):
        raise ValidationError("AuditEvent tidak boleh dihapus")


class AuditEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source_id = models.CharField(max_length=120, null=True, blank=True, unique=True)
    source_previous_hash = models.CharField(max_length=64, blank=True)
    source_event_hash = models.CharField(max_length=64, blank=True)
    occurred_at = models.DateTimeField(default=timezone.now, editable=False, db_index=True)
    actor_id = models.CharField(max_length=64, blank=True)
    actor_label = models.CharField(max_length=160, blank=True)
    actor_scope = models.CharField(max_length=160, blank=True)
    actor_role = models.CharField(max_length=40, blank=True)
    assignment_reference = models.CharField(max_length=80, blank=True)
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
    previous_hash = models.CharField(max_length=64, blank=True)
    integrity_hash = models.CharField(max_length=64, blank=True)
    retention_until = models.DateField(null=True, blank=True)

    objects = models.Manager.from_queryset(AppendOnlyAuditQuerySet)()

    def canonical_payload(self) -> dict:
        return {
            "id": str(self.id),
            "actor_id": self.actor_id,
            "actor_label": self.actor_label,
            "actor_scope": self.actor_scope,
            "actor_role": self.actor_role,
            "assignment_reference": self.assignment_reference,
            "action": self.action,
            "object_type": self.object_type,
            "object_id": self.object_id,
            "summary": self.summary,
            "before": self.before,
            "after": self.after,
            "reason": self.reason,
            "correlation_id": str(self.correlation_id),
            "ip_address": str(self.ip_address or ""),
            "user_agent": self.user_agent,
            "outcome": self.outcome,
            "occurred_at": self.occurred_at.isoformat(),
            "retention_until": str(self.retention_until or ""),
            "previous_hash": self.previous_hash,
        }

    def expected_hash(self) -> str:
        canonical = json.dumps(
            self.canonical_payload(), sort_keys=True, separators=(",", ":"), default=str
        )
        return hashlib.sha256(canonical.encode()).hexdigest()

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("AuditEvent bersifat append-only")
        if not self.previous_hash:
            previous = (
                type(self).objects.order_by("-occurred_at", "-id").only("integrity_hash").first()
            )
            self.previous_hash = previous.integrity_hash if previous else "0" * 64
        if not self.integrity_hash:
            self.integrity_hash = self.expected_hash()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("AuditEvent tidak boleh dihapus")

    class Meta:
        ordering = ["-occurred_at"]
        indexes = [models.Index(fields=["object_type", "object_id", "occurred_at"])]


class AuditSensitivePayload(models.Model):
    audit = models.OneToOneField(
        AuditEvent,
        on_delete=models.PROTECT,
        related_name="sensitive_payload",
    )
    payload = models.JSONField(default=dict)
    classification = models.CharField(max_length=32, default="confidential")
    retention_until = models.DateField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)


class AuditReference(models.Model):
    source_type = models.CharField(max_length=80)
    source_id = models.CharField(max_length=80)
    audit = models.ForeignKey(AuditEvent, on_delete=models.PROTECT, related_name="references")
    label = models.CharField(max_length=120, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["source_type", "source_id", "audit"],
                name="audit_reference_unique",
            )
        ]


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
    authorization_snapshot = models.JSONField(default=dict, blank=True)
    feature_snapshot = models.JSONField(default=dict, blank=True)
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

    source_id = models.CharField(max_length=120, null=True, blank=True, unique=True)
    source_status = models.CharField(max_length=40, blank=True)
    source_snapshot = models.JSONField(default=dict, blank=True)
    code = models.SlugField(max_length=100)
    state = models.CharField(max_length=20, choices=State.choices, default=State.DISABLED)
    scope = models.JSONField(default=dict, blank=True)
    owner = models.CharField(max_length=160)
    activation_date = models.DateTimeField(null=True, blank=True)
    target_users = models.JSONField(default=list, blank=True)
    acceptance_evidence = models.TextField(blank=True)
    rollback_plan = models.TextField(blank=True)
    kill_switch = models.BooleanField(default=False)

    def clean(self):
        super().clean()
        valid_scope = {"global", "module", "roles", "cohorts", "courses", "environment"}
        if set(self.scope) - valid_scope:
            raise ValidationError("Scope feature flag tidak dikenal")
        enabled = self.state not in {self.State.DISABLED, self.State.RETIRED}
        if enabled and not all(
            [
                self.owner.strip(),
                self.activation_date,
                self.target_users,
                self.acceptance_evidence.strip(),
                self.rollback_plan.strip(),
            ]
        ):
            raise ValidationError(
                "Aktivasi feature flag memerlukan owner, tanggal, target, evidence, dan rollback"
            )

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
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="rules_reviewed",
    )
    activated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="rules_activated",
    )
    review_note = models.TextField(blank=True)
    activated_at = models.DateTimeField(null=True, blank=True)

    def clean(self):
        super().clean()
        if not self.code.strip() or not self.input_schema or not self.expression:
            raise ValidationError("Rule memerlukan code, input schema, dan expression")
        if self.severity not in {"blocking", "warning", "information"}:
            raise ValidationError("Severity rule tidak dikenal")
        if self.status in {self.Status.REVIEWED, self.Status.ACTIVE} and not self.reviewed_by_id:
            raise ValidationError("Rule reviewed/active memerlukan reviewer")
        if self.status == self.Status.ACTIVE:
            if not self.activated_by_id or not self.activated_at:
                raise ValidationError("Rule aktif memerlukan checker dan waktu aktivasi")
            if self.created_by_id == self.activated_by_id:
                raise ValidationError("Maker dan checker rule harus berbeda")

    def save(self, *args, **kwargs):
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).first()
            if previous and previous.status == self.Status.ACTIVE:
                old = {
                    field.name: getattr(previous, field.name)
                    for field in self._meta.concrete_fields
                    if field.name not in {"status", "updated_at"}
                }
                new = {
                    field.name: getattr(self, field.name)
                    for field in self._meta.concrete_fields
                    if field.name not in {"status", "updated_at"}
                }
                if old != new or self.status not in {self.Status.ACTIVE, self.Status.RETIRED}:
                    raise ValidationError("Versi rule aktif bersifat immutable")
        self.clean()
        return super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["code", "version"], name="rule_version_unique")
        ]


class CohortRulePackage(VersionedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        REVIEWED = "reviewed", "Reviewed"
        ACTIVE = "active", "Active"
        RETIRED = "retired", "Retired"

    code = models.CharField(max_length=80)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    cohort_from = models.PositiveSmallIntegerField()
    cohort_to = models.PositiveSmallIntegerField(null=True, blank=True)
    grade_scheme = models.JSONField(default=list)
    minimum_passing_grade = models.CharField(max_length=4, default="C")
    minimum_thesis_grade = models.CharField(max_length=4, default="B")
    irs_policy = models.JSONField(default=dict, blank=True)
    progress_milestones = models.JSONField(default=list, blank=True)
    graduation_policy = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="rule_packages_created",
    )
    activated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="rule_packages_activated",
    )
    activated_at = models.DateTimeField(null=True, blank=True)

    def clean(self):
        super().clean()
        if self.cohort_to is not None and self.cohort_to < self.cohort_from:
            raise ValidationError("Rentang cohort package tidak valid")
        if not self.grade_scheme:
            raise ValidationError("Package memerlukan grade scheme")
        if self.status == self.Status.ACTIVE:
            if not self.activated_by_id or not self.activated_at:
                raise ValidationError("Package aktif memerlukan checker dan waktu aktivasi")
            if self.created_by_id == self.activated_by_id:
                raise ValidationError("Maker dan checker package harus berbeda")

    def save(self, *args, **kwargs):
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).first()
            if previous and previous.status == self.Status.ACTIVE:
                old = {
                    field.name: getattr(previous, field.name)
                    for field in self._meta.concrete_fields
                    if field.name not in {"status", "updated_at"}
                }
                new = {
                    field.name: getattr(self, field.name)
                    for field in self._meta.concrete_fields
                    if field.name not in {"status", "updated_at"}
                }
                if old != new or self.status not in {self.Status.ACTIVE, self.Status.RETIRED}:
                    raise ValidationError("Package aktif bersifat immutable")
        self.clean()
        return super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["code", "version"], name="rule_package_version_unique")
        ]


class AcademicDecision(models.Model):
    class Outcome(models.TextChoices):
        PASS = "pass", "Pass"
        FAIL = "fail", "Fail"
        INDETERMINATE = "indeterminate", "Indeterminate"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    object_type = models.CharField(max_length=80, db_index=True)
    object_id = models.CharField(max_length=80, db_index=True)
    rule = models.ForeignKey(AcademicRule, on_delete=models.PROTECT, related_name="decisions")
    package = models.ForeignKey(
        CohortRulePackage,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="decisions",
    )
    outcome = models.CharField(max_length=20, choices=Outcome.choices)
    reason_code = models.CharField(max_length=100, db_index=True)
    evidence_rows = models.JSONField(default=list)
    input_snapshot = models.JSONField(default=dict)
    calculation_trace = models.JSONField(default=list)
    source_versions = models.JSONField(default=dict, blank=True)
    explanation = models.TextField()
    input_hash = models.CharField(max_length=64, db_index=True)
    decision_hash = models.CharField(max_length=64, unique=True)
    correlation_id = models.UUIDField(default=uuid.uuid4, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Decision snapshot bersifat immutable")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Decision snapshot tidak boleh dihapus")

    class Meta:
        indexes = [models.Index(fields=["object_type", "object_id", "created_at"])]


class DecisionOverride(TimeStampedModel):
    class Status(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        REVIEWED = "reviewed", "Reviewed"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        EXPIRED = "expired", "Expired"
        REVOKED = "revoked", "Revoked"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source_id = models.CharField(max_length=120, null=True, blank=True, unique=True)
    source_status = models.CharField(max_length=40, blank=True)
    source_snapshot = models.JSONField(default=dict, blank=True)
    decision = models.ForeignKey(
        AcademicDecision, on_delete=models.PROTECT, related_name="overrides"
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SUBMITTED)
    reason_code = models.CharField(max_length=100)
    reason = models.TextField()
    evidence_documents = models.JSONField(default=list)
    impact = models.TextField()
    valid_from = models.DateTimeField(default=timezone.now)
    valid_to = models.DateTimeField(null=True, blank=True)
    maker = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="overrides_made"
    )
    checker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="overrides_checked",
    )
    review_note = models.TextField(blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    def clean(self):
        if self.valid_to and self.valid_to <= self.valid_from:
            raise ValidationError("Masa berlaku override tidak valid")
        if not self.reason_code.strip() or not self.reason.strip() or not self.impact.strip():
            raise ValidationError("Override memerlukan reason code, alasan, dan dampak")
        if not self.evidence_documents:
            raise ValidationError("Override memerlukan dokumen bukti")
        if self.checker_id and self.checker_id == self.maker_id:
            raise ValidationError("Maker tidak boleh menyetujui override sendiri")
        if self.status in {self.Status.APPROVED, self.Status.REJECTED} and not self.checker_id:
            raise ValidationError("Keputusan override memerlukan checker")


class AcademicAppeal(TimeStampedModel):
    class Status(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        REVIEWED = "reviewed", "Reviewed"
        INFORMATION_NEEDED = "information-needed", "Information needed"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        EXPIRED = "expired", "Expired"
        CLOSED = "closed", "Closed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    decision = models.ForeignKey(AcademicDecision, on_delete=models.PROTECT, related_name="appeals")
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.SUBMITTED)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="appeals_submitted"
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="appeals_reviewed",
    )
    statement = models.TextField()
    evidence_documents = models.JSONField(default=list)
    information_request = models.TextField(blank=True)
    resolution = models.TextField(blank=True)
    expires_at = models.DateTimeField()
    closed_at = models.DateTimeField(null=True, blank=True)

    def clean(self):
        if self.reviewed_by_id and self.reviewed_by_id == self.submitted_by_id:
            raise ValidationError("Pemohon banding tidak boleh menjadi reviewer")


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
    source_id = models.CharField(max_length=120, null=True, blank=True, unique=True)
    source_snapshot = models.JSONField(default=dict, blank=True)
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
