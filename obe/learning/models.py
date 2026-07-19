import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from obe.shared.models import TimeStampedModel, VersionedModel


class CourseOffering(VersionedModel):
    source_id = models.CharField(max_length=120, null=True, blank=True, unique=True)
    course_public_id = models.UUIDField(db_index=True)
    curriculum_version_public_id = models.UUIDField(null=True, blank=True, db_index=True)
    academic_year = models.CharField(max_length=12)
    semester = models.CharField(max_length=12)
    class_code = models.CharField(max_length=20)
    parallel_group = models.CharField(max_length=40, blank=True)
    coordinator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    lecturers = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name="offerings_taught", blank=True
    )
    schedule = models.JSONField(default=dict, blank=True)
    room = models.CharField(max_length=80, blank=True)
    capacity = models.PositiveIntegerField(default=40)
    status = models.CharField(max_length=20, default="draft")
    delivery_mode = models.CharField(
        max_length=16,
        choices=[("regular", "Regular"), ("short", "Short semester")],
        default="regular",
    )
    calendar_configuration = models.JSONField(default=dict, blank=True)
    starts_on = models.DateField(null=True, blank=True)
    ends_on = models.DateField(null=True, blank=True)

    def clean(self):
        super().clean()
        if self.starts_on and self.ends_on and self.ends_on < self.starts_on:
            raise ValidationError("Tanggal akhir penawaran tidak boleh sebelum tanggal mulai")
        if self.delivery_mode == "short" and not self.calendar_configuration:
            raise ValidationError("Semester pendek wajib memiliki konfigurasi kalender terpisah")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["course_public_id", "academic_year", "semester", "class_code"],
                name="offering_class_unique",
            )
        ]


class OfferingRoster(VersionedModel):
    class IRSStatus(models.TextChoices):
        APPROVED = "approved", "Approved"
        PENDING = "pending", "Pending"
        MISSING = "missing", "Missing"
        REJECTED = "rejected", "Rejected"

    offering = models.ForeignKey(
        CourseOffering, on_delete=models.PROTECT, related_name="roster_entries"
    )
    student_id = models.CharField(max_length=64)
    enrollment_plan_public_id = models.UUIDField(null=True, blank=True)
    irs_status = models.CharField(
        max_length=16, choices=IRSStatus.choices, default=IRSStatus.MISSING
    )
    status = models.CharField(
        max_length=16,
        choices=[("active", "Active"), ("withdrawn", "Withdrawn")],
        default="active",
    )
    source_version = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["offering", "student_id", "version"],
                name="offering_roster_student_version_unique",
            )
        ]


class RPSVersion(VersionedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        GPM_REVIEW = "gpm_review", "Review GPM"
        PRODI_APPROVAL = "prodi_approval", "Approval Prodi"
        PUBLISHED = "published", "Published"
        RETURNED = "returned", "Returned"

    offering = models.ForeignKey(
        CourseOffering, on_delete=models.PROTECT, related_name="rps_versions"
    )
    source_id = models.CharField(max_length=120, null=True, blank=True, unique=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.DRAFT)
    content = models.JSONField(default=dict)
    total_assessment_weight = models.DecimalField(max_digits=6, decimal_places=3, default=0)
    authored_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="rps_authored"
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="rps_reviewed",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="rps_approved",
    )
    approval_snapshot = models.JSONField(default=dict, blank=True)
    revision_reason = models.TextField(blank=True)
    returned_comment = models.TextField(blank=True)
    content_checksum = models.CharField(max_length=64, blank=True, db_index=True)
    reviewed_checksum = models.CharField(max_length=64, blank=True)
    approved_checksum = models.CharField(max_length=64, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)

    def clean(self):
        super().clean()
        if self.status == self.Status.PUBLISHED:
            if self.total_assessment_weight != 100:
                raise ValidationError("Total bobot asesmen harus tepat 100%")
            if not self.reviewed_by_id or not self.approved_by_id:
                raise ValidationError("Review GPM dan approval Prodi wajib")
            if self.authored_by_id in {self.reviewed_by_id, self.approved_by_id}:
                raise ValidationError("Self-approval tidak diizinkan")
            if not self.approved_checksum or self.approved_checksum != self.content_checksum:
                raise ValidationError("Approval stale; konten RPS berubah setelah persetujuan")
            if not self.published_at:
                raise ValidationError("Waktu publikasi wajib tersedia")

    def save(self, *args, **kwargs):
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).values("status").first()
            if previous and previous["status"] == self.Status.PUBLISHED:
                raise ValidationError("RPS published immutable; buat versi baru untuk perubahan")
        return super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["offering", "version"], name="rps_offering_version_unique"
            )
        ]


class CourseOutcome(VersionedModel):
    rps = models.ForeignKey(RPSVersion, on_delete=models.PROTECT, related_name="course_outcomes")
    code = models.CharField(max_length=24)
    description = models.TextField()
    bloom_level = models.CharField(max_length=32)
    target = models.DecimalField(max_digits=6, decimal_places=2, default=75)
    weight = models.DecimalField(max_digits=6, decimal_places=2)
    order = models.PositiveSmallIntegerField(default=1)
    program_cpmk_ids = models.JSONField(default=list)
    cpl_ids = models.JSONField(default=list)
    status = models.CharField(max_length=20, default="active")

    def clean(self):
        super().clean()
        if not self.code.strip() or not self.description.strip():
            raise ValidationError("Kode dan deskripsi CPMK-RPS wajib")
        if not Decimal("0") < self.weight <= Decimal("100"):
            raise ValidationError("Bobot CPMK-RPS harus >0 dan <=100")
        if not self.program_cpmk_ids or not self.cpl_ids:
            raise ValidationError("CPMK-RPS wajib terhubung ke CPMK program dan CPL")

    def save(self, *args, **kwargs):
        if (
            self.rps_id
            and RPSVersion.objects.filter(
                pk=self.rps_id, status=RPSVersion.Status.PUBLISHED
            ).exists()
        ):
            raise ValidationError("Desain RPS published immutable; buat versi baru")
        return super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["rps", "code"], name="rps_course_outcome_code_unique")
        ]


class SubOutcome(VersionedModel):
    rps = models.ForeignKey(RPSVersion, on_delete=models.PROTECT, related_name="sub_outcomes")
    course_outcome = models.ForeignKey(
        CourseOutcome, on_delete=models.PROTECT, related_name="sub_outcomes"
    )
    code = models.CharField(max_length=32)
    description = models.TextField()
    bloom_level = models.CharField(max_length=32)
    target = models.DecimalField(max_digits=6, decimal_places=2, default=75)
    weight = models.DecimalField(max_digits=6, decimal_places=2)
    order = models.PositiveSmallIntegerField(default=1)
    status = models.CharField(max_length=20, default="active")

    def clean(self):
        super().clean()
        if self.course_outcome_id and self.rps_id != self.course_outcome.rps_id:
            raise ValidationError("Sub-CPMK dan CPMK-RPS harus berada pada RPS yang sama")
        if not self.code.strip() or not self.description.strip():
            raise ValidationError("Kode dan deskripsi Sub-CPMK wajib")
        if not Decimal("0") < self.weight <= Decimal("100"):
            raise ValidationError("Bobot Sub-CPMK harus >0 dan <=100")

    def save(self, *args, **kwargs):
        if (
            self.rps_id
            and RPSVersion.objects.filter(
                pk=self.rps_id, status=RPSVersion.Status.PUBLISHED
            ).exists()
        ):
            raise ValidationError("Desain RPS published immutable; buat versi baru")
        return super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["rps", "code"], name="rps_sub_outcome_code_unique")
        ]


class PerformanceIndicator(VersionedModel):
    rps = models.ForeignKey(RPSVersion, on_delete=models.PROTECT, related_name="indicators")
    sub_outcome = models.ForeignKey(SubOutcome, on_delete=models.PROTECT, related_name="indicators")
    code = models.CharField(max_length=40)
    description = models.TextField()
    measurement = models.CharField(max_length=80, default="normalized-score-0-100")
    target = models.DecimalField(max_digits=6, decimal_places=2, default=75)
    observable = models.BooleanField(default=True)
    order = models.PositiveSmallIntegerField(default=1)
    status = models.CharField(max_length=20, default="active")

    def clean(self):
        super().clean()
        if self.sub_outcome_id and self.rps_id != self.sub_outcome.rps_id:
            raise ValidationError("Indikator dan Sub-CPMK harus berada pada RPS yang sama")
        if not self.code.strip() or not self.description.strip() or not self.observable:
            raise ValidationError("Indikator wajib berkode, terukur, dan observable")

    def save(self, *args, **kwargs):
        if (
            self.rps_id
            and RPSVersion.objects.filter(
                pk=self.rps_id, status=RPSVersion.Status.PUBLISHED
            ).exists()
        ):
            raise ValidationError("Desain RPS published immutable; buat versi baru")
        return super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["rps", "code"], name="rps_indicator_code_unique")
        ]


class RPSFieldComment(models.Model):
    rps = models.ForeignKey(RPSVersion, on_delete=models.PROTECT, related_name="field_comments")
    field_path = models.CharField(max_length=160)
    comment = models.TextField()
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="rps_comments_resolved",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def resolve(self, user):
        self.resolved_at = timezone.now()
        self.resolved_by = user
        self.save(update_fields=["resolved_at", "resolved_by"])


class WeeklyPlan(VersionedModel):
    rps = models.ForeignKey(RPSVersion, on_delete=models.PROTECT, related_name="weekly_plans")
    week = models.PositiveSmallIntegerField()
    meeting_type = models.CharField(max_length=20, default="regular")
    outcomes = models.JSONField(default=list)
    indicators = models.JSONField(default=list)
    material = models.TextField()
    methods = models.JSONField(default=list)
    activities = models.JSONField(default=list)
    assignment = models.JSONField(default=dict, blank=True)
    contact_minutes = models.PositiveIntegerField(default=100)
    structured_minutes = models.PositiveIntegerField(default=120)
    independent_minutes = models.PositiveIntegerField(default=120)
    planned_date = models.DateField(null=True, blank=True)
    actual = models.JSONField(default=dict, blank=True)
    rescheduled_from = models.DateField(null=True, blank=True)
    reschedule_reason = models.TextField(blank=True)
    rescheduled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="weekly_plans_rescheduled",
    )
    execution_recorded_at = models.DateTimeField(null=True, blank=True)

    def clean(self):
        super().clean()
        if not 1 <= self.week <= 16:
            raise ValidationError("Minggu reguler harus 1–16")
        if self.meeting_type == "regular" and not self.methods:
            raise ValidationError("Metode pembelajaran minggu reguler wajib")
        if self.planned_date and self.rps.offering.starts_on and self.rps.offering.ends_on:
            if not self.rps.offering.starts_on <= self.planned_date <= self.rps.offering.ends_on:
                raise ValidationError("Tanggal pertemuan di luar periode semester")

    def save(self, *args, **kwargs):
        if (
            self.pk
            and self.rps_id
            and RPSVersion.objects.filter(
                pk=self.rps_id, status=RPSVersion.Status.PUBLISHED
            ).exists()
        ):
            previous = type(self).objects.get(pk=self.pk)
            update_fields = set(kwargs.get("update_fields") or ())
            execution_fields = {
                "actual",
                "execution_recorded_at",
                "planned_date",
                "rescheduled_from",
                "reschedule_reason",
                "rescheduled_by",
                "updated_at",
            }
            if not update_fields or update_fields - execution_fields:
                raise ValidationError(
                    "Desain minggu published immutable; catat realisasi/reschedule"
                )
            if previous.planned_date != self.planned_date and (
                not self.reschedule_reason.strip() or not self.rescheduled_by_id
            ):
                raise ValidationError(
                    "Perubahan tanggal published wajib alasan dan aktor reschedule"
                )
        return super().save(*args, **kwargs)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["rps", "week"], name="rps_week_unique")]


class Attendance(models.Model):
    offering = models.ForeignKey(
        CourseOffering, on_delete=models.PROTECT, related_name="attendance"
    )
    student_id = models.CharField(max_length=64)
    activity_id = models.CharField(max_length=64)
    status = models.CharField(
        max_length=16,
        choices=[
            ("present", "Hadir"),
            ("late", "Terlambat"),
            ("permit", "Izin"),
            ("sick", "Sakit"),
            ("absent", "Alpa"),
            ("cancelled", "Dibatalkan"),
            ("exempt", "Pengecualian"),
        ],
    )
    occurred_at = models.DateTimeField()
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    note = models.TextField(blank=True)
    source_version = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["offering", "student_id", "activity_id"], name="attendance_once"
            )
        ]


class ExamEligibilityOverride(VersionedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        REVOKED = "revoked", "Revoked"

    roster = models.ForeignKey(
        OfferingRoster, on_delete=models.PROTECT, related_name="exam_overrides"
    )
    reason_code = models.CharField(max_length=80)
    reason = models.TextField()
    evidence_ids = models.JSONField(default=list)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="exam_overrides_requested",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="exam_overrides_approved",
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    expires_at = models.DateTimeField(null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    def clean(self):
        super().clean()
        if not self.reason_code.strip() or not self.reason.strip() or not self.evidence_ids:
            raise ValidationError("Override eligibility memerlukan reason code, alasan, dan bukti")
        if self.status == self.Status.APPROVED:
            if not self.approved_by_id or not self.decided_at:
                raise ValidationError("Override approved memerlukan approver dan waktu keputusan")
            if self.approved_by_id == self.requested_by_id:
                raise ValidationError("Pemohon tidak boleh menyetujui override sendiri")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["roster", "reason_code", "version"],
                name="exam_override_roster_reason_version_unique",
            )
        ]


class ExamEligibilitySnapshot(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    roster = models.ForeignKey(
        OfferingRoster, on_delete=models.PROTECT, related_name="eligibility_snapshots"
    )
    eligible = models.BooleanField()
    attendance_percent = models.DecimalField(max_digits=6, decimal_places=2)
    attended = models.PositiveIntegerField()
    denominator = models.PositiveIntegerField()
    counted_activity_ids = models.JSONField(default=list)
    reason_codes = models.JSONField(default=list)
    rule_code = models.CharField(max_length=80, default="ATTENDANCE-UAS-75")
    rule_version = models.PositiveIntegerField(default=1)
    override = models.ForeignKey(
        ExamEligibilityOverride,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="eligibility_snapshots",
    )
    source_versions = models.JSONField(default=dict)
    generated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        indexes = [models.Index(fields=["roster", "created_at"])]
