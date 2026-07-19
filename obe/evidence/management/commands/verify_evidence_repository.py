from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from obe.evidence.models import EvidenceRecord
from obe.evidence.services import verify_integrity


class Command(BaseCommand):
    help = "Verifikasi ulang checksum seluruh evidence terhadap manifest kanonik"

    def handle(self, *args, **options):
        invalid = []
        queryset = EvidenceRecord.objects.select_related("manifest").iterator(chunk_size=500)
        for record in queryset:
            if not verify_integrity(record):
                invalid.append(str(record.public_id))
        if invalid:
            raise CommandError(
                f"{len(invalid)} evidence gagal verifikasi di {settings.EVIDENCE_ROOT}"
            )
        self.stdout.write(self.style.SUCCESS("Seluruh evidence cocok dengan manifest."))
