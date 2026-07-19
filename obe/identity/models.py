import uuid

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
    source_id = models.CharField(max_length=80, null=True, blank=True, unique=True)
    source_public_id = models.UUIDField(null=True, blank=True, unique=True)
    source_status = models.CharField(max_length=24, blank=True)
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
        if (
            not isinstance(self.actions, list)
            or not self.actions
            or any(not isinstance(action, str) or not action.strip() for action in self.actions)
        ):
            raise ValidationError("Assignment wajib memiliki daftar aksi valid")
        if self.scope_id != "*" and not self.scope_id.strip():
            raise ValidationError("Scope assignment tidak valid")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "role", "scope_type", "scope_id", "period"],
                condition=models.Q(revoked_at__isnull=True),
                name="active_assignment_unique",
            )
        ]


class LecturerProfile(TimeStampedModel):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="lecturer_profile",
    )
    lecturer_id = models.CharField(max_length=32, unique=True)
    display_name = models.CharField(max_length=160)
    expertise = models.TextField(blank=True)
    expertise_tags = models.JSONField(default=list, blank=True)
    identity_source = models.CharField(max_length=32, blank=True)
    source_status = models.CharField(max_length=24, blank=True)
    workload_summary = models.JSONField(default=dict, blank=True)

    def clean(self):
        if not self.lecturer_id.strip() or not self.display_name.strip():
            raise ValidationError("Identitas dan nama dosen wajib")
        if not isinstance(self.expertise_tags, list):
            raise ValidationError("Tag keahlian dosen harus berupa daftar")

    class Meta:
        indexes = [models.Index(fields=["identity_source", "source_status"])]


class AccountSecurity(TimeStampedModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="security_profile",
    )
    failed_attempts = models.PositiveSmallIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True, db_index=True)
    password_reset_required = models.BooleanField(default=False)
    mfa_enabled = models.BooleanField(default=False)
    mfa_enrolled_at = models.DateTimeField(null=True, blank=True)
    permission_epoch = models.PositiveIntegerField(default=1)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)

    @property
    def locked(self) -> bool:
        return self.locked_until is not None and self.locked_until > timezone.now()

    def clean(self):
        if self.mfa_enabled and self.mfa_enrolled_at is None:
            raise ValidationError("MFA aktif wajib memiliki waktu enrollment")


class MFAChallenge(TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    token_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField(db_index=True)
    consumed_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)

    @property
    def usable(self) -> bool:
        return self.consumed_at is None and self.expires_at > timezone.now() and self.attempts < 5

    class Meta:
        indexes = [models.Index(fields=["user", "expires_at"])]
