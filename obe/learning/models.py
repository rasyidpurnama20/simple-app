from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from obe.shared.models import VersionedModel


class CourseOffering(VersionedModel):
    course_public_id = models.UUIDField(db_index=True)
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

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["course_public_id", "academic_year", "semester", "class_code"],
                name="offering_class_unique",
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

    def clean(self):
        if self.status == self.Status.PUBLISHED:
            if self.total_assessment_weight != 100:
                raise ValidationError("Total bobot asesmen harus tepat 100%")
            if not self.reviewed_by_id or not self.approved_by_id:
                raise ValidationError("Review GPM dan approval Prodi wajib")
            if self.authored_by_id in {self.reviewed_by_id, self.approved_by_id}:
                raise ValidationError("Self-approval tidak diizinkan")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["offering", "version"], name="rps_offering_version_unique"
            )
        ]


class WeeklyPlan(VersionedModel):
    rps = models.ForeignKey(RPSVersion, on_delete=models.PROTECT, related_name="weekly_plans")
    week = models.PositiveSmallIntegerField()
    meeting_type = models.CharField(max_length=20, default="regular")
    outcomes = models.JSONField(default=list)
    indicators = models.JSONField(default=list)
    material = models.TextField()
    methods = models.JSONField(default=list)
    activities = models.JSONField(default=list)
    contact_minutes = models.PositiveIntegerField(default=100)
    structured_minutes = models.PositiveIntegerField(default=120)
    independent_minutes = models.PositiveIntegerField(default=120)
    planned_date = models.DateField(null=True, blank=True)
    actual = models.JSONField(default=dict, blank=True)

    def clean(self):
        if not 1 <= self.week <= 16:
            raise ValidationError("Minggu reguler harus 1–16")

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

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["offering", "student_id", "activity_id"], name="attendance_once"
            )
        ]
