import uuid

from django.core.exceptions import ValidationError
from django.db import models

from obe.shared.models import TimeStampedModel


class EvidenceRecord(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        VERIFIED = "verified", "Verified"
        REJECTED = "rejected", "Rejected"
        SUPERSEDED = "superseded", "Superseded"
        ARCHIVED = "archived", "Archived"

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    manifest = models.OneToOneField("shared.FileManifest", on_delete=models.PROTECT)
    object_type = models.CharField(max_length=80)
    object_id = models.CharField(max_length=80)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    verified_by_id = models.CharField(max_length=64, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    supersedes = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT)

    def save(self, *args, **kwargs):
        if self.pk:
            previous = (
                type(self)
                .objects.filter(pk=self.pk)
                .values("status", "manifest_id", "object_type", "object_id")
                .first()
            )
            if previous and previous["status"] == self.Status.VERIFIED:
                immutable_changed = (
                    previous["manifest_id"] != self.manifest_id
                    or previous["object_type"] != self.object_type
                    or previous["object_id"] != self.object_id
                )
                if immutable_changed or self.status not in {
                    self.Status.VERIFIED,
                    self.Status.SUPERSEDED,
                    self.Status.ARCHIVED,
                }:
                    raise ValidationError("Bukti verified tidak dapat ditimpa")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.status == self.Status.VERIFIED:
            raise ValidationError("Bukti verified tidak boleh dihapus")
        return super().delete(*args, **kwargs)

    class Meta:
        indexes = [models.Index(fields=["object_type", "object_id", "status"])]
