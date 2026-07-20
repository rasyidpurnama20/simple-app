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

    source_id = models.CharField(max_length=120, null=True, blank=True, unique=True)
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
    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        ACTIVE = "active", "Active"
        BLOCKED = "blocked", "Blocked"
        COMPLETED = "completed", "Completed"
        INEFFECTIVE = "ineffective", "Ineffective"
        EFFECTIVE = "effective", "Effective"
        ACCEPTED_RISK = "accepted-risk", "Accepted risk"
        REOPENED = "reopened", "Reopened"

    issue = models.ForeignKey(
        IntegrityIssue,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="actions",
    )
    finding = models.ForeignKey(
        "QualityFinding",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="actions",
    )
    root_cause = models.TextField()
    action = models.TextField()
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    due_at = models.DateTimeField()
    success_indicator = models.TextField()
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.PLANNED)
    baseline = models.JSONField(default=dict)
    result = models.JSONField(default=dict, blank=True)
    approval = models.JSONField(default=dict, blank=True)
    evidence = models.JSONField(default=list, blank=True)
    accepted_risk_reason = models.TextField(blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    evaluated_at = models.DateTimeField(null=True, blank=True)
    reopened_count = models.PositiveSmallIntegerField(default=0)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="improvement_actions_approved",
    )

    def clean(self):
        super().clean()
        if bool(self.issue_id) == bool(self.finding_id):
            raise ValidationError("Tindakan harus terhubung tepat ke issue atau finding")
        if self.status == self.Status.ACCEPTED_RISK and not self.accepted_risk_reason.strip():
            raise ValidationError("Accepted risk memerlukan alasan")
        if self.status in {self.Status.COMPLETED, self.Status.EFFECTIVE} and not self.evidence:
            raise ValidationError("Tindakan selesai memerlukan bukti")


class QualityStandard(VersionedModel):
    source_id = models.CharField(max_length=120, unique=True)
    code = models.CharField(max_length=80)
    metric = models.CharField(max_length=80)
    target = models.DecimalField(max_digits=8, decimal_places=2)
    source_snapshot = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["code", "version"], name="quality_standard_code_version_unique"
            )
        ]


class QualityFinding(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source_id = models.CharField(max_length=160, unique=True)
    standard = models.ForeignKey(QualityStandard, on_delete=models.PROTECT, related_name="findings")
    scope = models.JSONField(default=dict)
    actual = models.DecimalField(max_digits=8, decimal_places=2)
    target = models.DecimalField(max_digits=8, decimal_places=2)
    gap = models.DecimalField(max_digits=8, decimal_places=2)
    classification = models.CharField(max_length=40)
    denominator = models.PositiveIntegerField(default=0)
    coverage = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    confidence = models.CharField(max_length=24, default="unknown")
    status = models.CharField(max_length=24, default="open")
    reason_codes = models.JSONField(default=list, blank=True)
    source_snapshot = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class PortfolioSnapshot(VersionedModel):
    class PortfolioType(models.TextChoices):
        STUDENT = "student", "Student"
        COURSE = "course", "Course"
        PROGRAM = "program", "Program"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        GPM_REVIEW = "gpm-review", "GPM review"
        RETURNED = "returned", "Returned for revision"
        APPROVED = "approved", "Approved"
        PUBLISHED = "published", "Published"
        SUPERSEDED = "superseded", "Superseded"
        ARCHIVED = "archived", "Archived"

    portfolio_type = models.CharField(max_length=16, choices=PortfolioType.choices)
    scope_id = models.CharField(max_length=120)
    period = models.CharField(max_length=40)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.DRAFT)
    sections = models.JSONField(default=dict)
    source_versions = models.JSONField(default=dict, blank=True)
    evidence_manifest_ids = models.JSONField(default=list, blank=True)
    incomplete_sections = models.JSONField(default=list, blank=True)
    package_checksum = models.CharField(max_length=64)
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="portfolios_generated",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="portfolios_reviewed",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="portfolios_approved",
    )
    published_at = models.DateTimeField(null=True, blank=True)
    approval_history = models.JSONField(default=list, blank=True)
    supersedes = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="superseded_by",
    )

    def clean(self):
        super().clean()
        if len(self.package_checksum) != 64:
            raise ValidationError("Portfolio memerlukan checksum SHA-256")
        if self.status in {self.Status.APPROVED, self.Status.PUBLISHED}:
            if self.incomplete_sections or not self.approved_by_id:
                raise ValidationError("Portfolio belum lengkap atau belum memiliki approver")
            if self.generated_by_id == self.approved_by_id:
                raise ValidationError("Pembuat portfolio tidak boleh menjadi approver")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["portfolio_type", "scope_id", "period", "version"],
                name="portfolio_scope_period_version_unique",
            )
        ]


class QualityReport(VersionedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        GPM_REVIEWED = "gpm-reviewed", "GPM reviewed"
        PRODI_APPROVED = "prodi-approved", "Prodi approved"
        TPMF_REVIEWED = "tpmf-reviewed", "TPMF reviewed"
        PUBLISHED = "published", "Published"
        CORRECTION = "correction", "Correction"

    cycle = models.ForeignKey(QualityCycle, on_delete=models.PROTECT, related_name="reports")
    period = models.CharField(max_length=40)
    scope_type = models.CharField(max_length=40)
    scope_id = models.CharField(max_length=80)
    evaluation_type = models.CharField(max_length=16, default="formative")
    sections = models.JSONField(default=dict)
    source_versions = models.JSONField(default=dict, blank=True)
    missing_sections = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.DRAFT)
    package_checksum = models.CharField(max_length=64)
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="quality_reports_generated",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="quality_reports_reviewed",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="quality_reports_approved",
    )
    tpmf_reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="quality_reports_tpmf_reviewed",
    )
    approval_history = models.JSONField(default=list, blank=True)
    correction_of = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="corrections",
    )
    published_at = models.DateTimeField(null=True, blank=True)

    def clean(self):
        super().clean()
        if len(self.package_checksum) != 64:
            raise ValidationError("Laporan mutu memerlukan checksum SHA-256")
        if self.status == self.Status.PUBLISHED:
            actors = {
                self.generated_by_id,
                self.reviewed_by_id,
                self.approved_by_id,
                self.tpmf_reviewer_id,
            }
            if None in actors or len(actors) != 4 or self.missing_sections:
                raise ValidationError("Laporan published memerlukan empat aktor dan data lengkap")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["period", "scope_type", "scope_id", "version"],
                name="quality_report_scope_period_version_unique",
            )
        ]


class AcademicFeedback(VersionedModel):
    class Status(models.TextChoices):
        NEW = "new", "New"
        VERIFIED = "verified", "Verified"
        CLARIFICATION = "clarification", "Clarification"
        ACTION_PLANNED = "action-planned", "Action planned"
        ACTIONED = "actioned", "Actioned"
        REJECTED = "rejected", "Rejected"
        CLOSED = "closed", "Closed"
        REOPENED = "reopened", "Reopened"

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="academic_feedback_submitted",
    )
    reporter_fingerprint = models.CharField(max_length=64, blank=True)
    anonymous = models.BooleanField(default=False)
    retaliation_risk = models.BooleanField(default=False)
    confidentiality = models.CharField(max_length=24, default="internal")
    period = models.CharField(max_length=40)
    course_offering_id = models.CharField(max_length=120, blank=True)
    category = models.CharField(max_length=40)
    description = models.TextField()
    evidence = models.JSONField(default=list, blank=True)
    impact = models.TextField()
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.NEW)
    responsible = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="academic_feedback_responsible",
    )
    due_at = models.DateTimeField(null=True, blank=True)
    linked_objects = models.JSONField(default=list, blank=True)
    decision_reason = models.TextField(blank=True)
    closure_evidence = models.JSONField(default=list, blank=True)
    fingerprint = models.CharField(max_length=64, db_index=True)

    def clean(self):
        super().clean()
        if not self.description.strip() or not self.impact.strip():
            raise ValidationError("Masukan memerlukan uraian dan dampak")
        if self.anonymous and self.reporter_id:
            raise ValidationError("Identitas reporter anonim tidak boleh disimpan")
        if self.retaliation_risk and self.confidentiality not in {"confidential", "restricted"}:
            raise ValidationError("Risiko retaliasi wajib diperlakukan confidential/restricted")
        if self.status == self.Status.CLOSED and not self.closure_evidence:
            raise ValidationError("Penutupan masukan memerlukan bukti")
