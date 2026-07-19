from django.conf import settings
from django.db import models

from obe.shared.models import VersionedModel


class StudentProfile(VersionedModel):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    student_number = models.CharField(max_length=32, unique=True)
    cohort = models.PositiveSmallIntegerField()
    curriculum_public_id = models.UUIDField()
    rule_package = models.CharField(max_length=32, default="CURRENT-AABBC")


class AcademicStatus(VersionedModel):
    student = models.ForeignKey(StudentProfile, on_delete=models.PROTECT, related_name="statuses")
    status = models.CharField(
        max_length=24,
        choices=[
            ("candidate", "Calon"),
            ("active", "Aktif"),
            ("absent", "Mangkir"),
            ("leave", "Cuti"),
            ("suspended", "Skorsing"),
            ("transfer", "Pindah"),
            ("dropout", "Putus Studi"),
            ("graduated", "Lulus"),
            ("withdrawn", "Mengundurkan Diri"),
            ("deceased", "Wafat"),
        ],
    )
    reason = models.TextField()
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    documents = models.JSONField(default=list)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["student", "effective_from", "version"], name="student_status_period_unique"
            )
        ]


class EnrollmentPlan(VersionedModel):
    student = models.ForeignKey(StudentProfile, on_delete=models.PROTECT, related_name="plans")
    academic_year = models.CharField(max_length=12)
    semester = models.PositiveSmallIntegerField()
    course_public_ids = models.JSONField(default=list)
    total_credits = models.PositiveSmallIntegerField(default=0)
    decision_snapshot = models.JSONField(default=dict)
    status = models.CharField(max_length=24, default="draft")
    advisor_id = models.CharField(max_length=64, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["student", "academic_year", "semester", "version"],
                name="student_plan_version_unique",
            )
        ]


class AcademicResult(VersionedModel):
    student = models.ForeignKey(StudentProfile, on_delete=models.PROTECT, related_name="results")
    course_public_id = models.UUIDField()
    academic_year = models.CharField(max_length=12)
    semester = models.PositiveSmallIntegerField()
    attempt = models.PositiveSmallIntegerField(default=1)
    credits = models.PositiveSmallIntegerField()
    letter = models.CharField(max_length=3)
    grade_point = models.DecimalField(max_digits=3, decimal_places=2, null=True)
    passed = models.BooleanField(default=False)
    source_type = models.CharField(max_length=24, default="regular")
    trace = models.JSONField(default=dict)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["student", "course_public_id", "attempt"], name="result_attempt_unique"
            )
        ]


class TaskInstance(VersionedModel):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="obe_tasks"
    )
    code = models.CharField(max_length=80)
    title = models.CharField(max_length=200)
    entity_type = models.CharField(max_length=80)
    entity_id = models.CharField(max_length=80)
    due_at = models.DateTimeField()
    status = models.CharField(max_length=24, default="not-started")
    priority = models.PositiveSmallIntegerField(default=3)
    dependency_ids = models.JSONField(default=list)
    required_evidence = models.JSONField(default=list)
    idempotency_key = models.CharField(max_length=160, unique=True)
    completed_at = models.DateTimeField(null=True, blank=True)


class Notification(models.Model):
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    task = models.ForeignKey(TaskInstance, null=True, blank=True, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    body = models.TextField()
    idempotency_key = models.CharField(max_length=160, unique=True)
    scheduled_at = models.DateTimeField()
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    snoozed_until = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
