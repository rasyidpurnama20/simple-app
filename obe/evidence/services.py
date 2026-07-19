import hashlib
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction

from obe.evidence.models import EvidenceRecord
from obe.shared.models import FileManifest

ALLOWED_MIME = {"application/pdf", "image/png", "image/jpeg", "text/csv"}
MAX_SIZE = 25 * 1024 * 1024


@transaction.atomic
def store(*, uploaded, owner_id: str, academic_object: str, classification: str) -> EvidenceRecord:
    if uploaded.size > MAX_SIZE:
        raise ValidationError("Ukuran bukti melebihi 25 MiB")
    if uploaded.content_type not in ALLOWED_MIME:
        raise ValidationError("Tipe file tidak diizinkan")
    digest = hashlib.sha256()
    for chunk in uploaded.chunks():
        digest.update(chunk)
    sha = digest.hexdigest()
    target = Path(settings.EVIDENCE_ROOT) / sha[:2] / sha[2:4] / sha
    target.parent.mkdir(parents=True, exist_ok=True)
    uploaded.seek(0)
    with target.open("xb") as handle:
        for chunk in uploaded.chunks():
            handle.write(chunk)
    manifest = FileManifest.objects.create(
        sha256=sha,
        size=uploaded.size,
        mime_type=uploaded.content_type,
        owner_id=owner_id,
        academic_object=academic_object,
        classification=classification,
        content_path=str(target.relative_to(settings.EVIDENCE_ROOT)),
    )
    return EvidenceRecord.objects.create(
        manifest=manifest,
        object_type=academic_object.split(":", 1)[0],
        object_id=academic_object.split(":", 1)[-1],
    )
