from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from obe.shared.models import TimeStampedModel


class RoleAssignment(TimeStampedModel):
    class Role(models.TextChoices):
        PROGRAM = "prodi", "Program Studi"
        QUALITY = "gpm", "GPM"
        LECTURER = "pengampu", "Pengampu"
        STUDENT = "mahasiswa", "Mahasiswa"
        ADVISOR = "dpa", "DPA"
        COORDINATOR = "koordinator", "Koordinator"
        SUPERVISOR = "pembimbing", "Pembimbing"
        EXAMINER = "penguji", "Penguji"
        MENTOR = "mentor", "Mentor"
        TPMF = "tpmf", "TPMF"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.CharField(max_length=24, choices=Role.choices)
    scope_type = models.CharField(max_length=80, default="global")
    scope_id = models.CharField(max_length=80, default="*")
    actions = models.JSONField(default=list)
    period = models.CharField(max_length=40, blank=True)
    starts_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="assignments_granted",
    )

    @property
    def active(self) -> bool:
        now = timezone.now()
        return (
            self.revoked_at is None
            and self.starts_at <= now
            and (self.expires_at is None or self.expires_at > now)
        )

    def clean(self):
        if self.user_id == self.granted_by_id:
            raise ValidationError("Self-assignment tidak diizinkan")
        if self.expires_at and self.expires_at <= self.starts_at:
            raise ValidationError("Expiry harus setelah waktu mulai")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "role", "scope_type", "scope_id", "period"],
                condition=models.Q(revoked_at__isnull=True),
                name="active_assignment_unique",
            )
        ]
