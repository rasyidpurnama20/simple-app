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
                type(self).objects.filter(pk=self.pk).values_list("status", flat=True).first()
            )
            if previous == self.Status.VERIFIED and self.status not in {
                self.Status.VERIFIED,
                self.Status.SUPERSEDED,
                self.Status.ARCHIVED,
            }:
                raise ValidationError("Bukti verified tidak dapat ditimpa")
        return super().save(*args, **kwargs)
