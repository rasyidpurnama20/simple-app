from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from obe.shared.models import VersionedModel


class Exam(VersionedModel):
    source_id = models.CharField(max_length=120, null=True, blank=True, unique=True)
    source_status = models.CharField(max_length=40, blank=True)
    source_snapshot = models.JSONField(default=dict, blank=True)
    offering_public_id = models.UUIDField()
    title = models.CharField(max_length=200)
    blueprint = models.JSONField(default=dict)
    item_versions = models.JSONField(default=list)
    roster_hash = models.CharField(max_length=64)
    duration_minutes = models.PositiveSmallIntegerField()
    policies = models.JSONField(default=dict)
    classification = models.CharField(max_length=32, default="restricted-exam")
    status = models.CharField(max_length=24, default="draft")
    authored_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="exams_authored"
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name="exams_reviewed"
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name="exams_approved"
    )
    signature = models.CharField(max_length=128, blank=True)

    def clean(self):
        if self.status == "released":
            actors = {self.authored_by_id, self.reviewed_by_id, self.approved_by_id}
            if None in actors or len(actors) != 3:
                raise ValidationError("Author, reviewer, dan approver harus tiga aktor berbeda")


class ExamSession(VersionedModel):
    exam = models.ForeignKey(Exam, on_delete=models.PROTECT, related_name="sessions")
    participant_id = models.CharField(max_length=80)
    session_code_hash = models.CharField(max_length=64)
    device_id = models.CharField(max_length=80)
    seat = models.CharField(max_length=20, blank=True)
    state = models.CharField(max_length=24, default="issued")
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    finalized_at = models.DateTimeField(null=True, blank=True)
    incident_log = models.JSONField(default=list)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["exam", "participant_id"], name="exam_participant_unique"
            ),
            models.UniqueConstraint(
                fields=["exam", "device_id"],
                condition=models.Q(state__in=["active", "reconnected"]),
                name="active_exam_device_unique",
            ),
        ]


class ExamResponse(models.Model):
    session = models.ForeignKey(ExamSession, on_delete=models.PROTECT, related_name="responses")
    item_id = models.CharField(max_length=80)
    version = models.PositiveIntegerField()
    idempotency_key = models.CharField(max_length=160, unique=True)
    response_ciphertext = models.TextField()
    checksum = models.CharField(max_length=64)
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["session", "item_id", "version"], name="exam_response_version_unique"
            )
        ]
