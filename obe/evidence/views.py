from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_POST

from obe.evidence.models import EvidenceRecord
from obe.evidence.services import issue_download_token, resolve_download


@login_required
@require_POST
def issue_token(request, public_id):
    record = get_object_or_404(
        EvidenceRecord.objects.select_related("manifest"), public_id=public_id
    )
    return JsonResponse(
        {
            "token": issue_download_token(record, request.user),
            "expires_in": settings.EVIDENCE_DOWNLOAD_TTL_SECONDS,
        }
    )


@login_required
@require_GET
def download(request, public_id):
    record = resolve_download(request.GET.get("token", ""), request.user)
    if record.public_id != public_id:
        return JsonResponse({"error": "Token tidak sesuai bukti"}, status=403)
    target = Path(settings.EVIDENCE_ROOT) / record.manifest.content_path
    extension = {
        "application/pdf": ".pdf",
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "text/csv": ".csv",
    }.get(record.manifest.mime_type, "")
    return FileResponse(
        target.open("rb"),
        as_attachment=True,
        filename=f"evidence-{record.public_id}{extension}",
        content_type=record.manifest.mime_type,
    )
