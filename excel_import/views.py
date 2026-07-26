"""Thin HTMX views for Excel Import (Requirement 9.2).

All business logic is in the service layer. Views parse input and call the
facade, then render templates.
"""

from __future__ import annotations

from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from core.exceptions import DomainError as CoreDomainError

from .errors import DomainError
from .services import ExcelImportService


def _get_service() -> ExcelImportService:
    return ExcelImportService()


def excel_import_workspace(request):
    """Render the Excel Import workspace overview."""
    from .models import ImportBatch
    batches = list(ImportBatch.objects.all()[:20])
    service = _get_service()
    types = service.registry.list_types()
    return render(request, "excel_import/workspace.html", {
        "batches": batches,
        "types": types,
        "active_workspace": "learning",
    })


def generate_template(request):
    """Generate and download a template .xlsx file."""
    template_type = request.GET.get("type", "Curriculum")
    service = _get_service()
    try:
        xlsx_bytes = service.generate_workbook(template_type)
        response = HttpResponse(
            xlsx_bytes,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="template_{template_type}.xlsx"'
        return response
    except DomainError as e:
        from django.contrib import messages
        messages.error(request, str(e))
        return redirect("excel_import:workspace")


@require_POST
def upload_and_dry_run(request):
    """Upload a file, validate, and run dry-run."""
    from django.contrib import messages

    uploaded = request.FILES.get("file")
    if not uploaded:
        messages.error(request, "Tidak ada file yang diunggah.")
        return redirect("excel_import:workspace")

    service = _get_service()
    file_bytes = uploaded.read()
    actor_id = getattr(request, "demo_user_id", None)

    try:
        report = service.upload_and_dry_run(
            file_bytes=file_bytes,
            declared_mime=uploaded.content_type or "",
            filename=uploaded.name or "",
            actor=actor_id,
        )
        return render(request, "excel_import/dry_run_report.html", {
            "report": report,
            "active_workspace": "learning",
        })
    except DomainError as e:
        messages.error(request, str(e))
        return redirect("excel_import:workspace")


@require_POST
def commit_batch(request):
    """Commit a validated batch."""
    from django.contrib import messages

    batch_id = request.POST.get("batch_id", "")
    service = _get_service()
    actor_id = getattr(request, "demo_user_id", None)

    try:
        summary = service.commit(batch_id, actor=actor_id)
        messages.success(
            request,
            f"Berhasil: {summary.inserted} ditambah, {summary.updated} diperbarui, "
            f"{summary.skipped} dilewati, {summary.rejected} ditolak.",
        )
    except DomainError as e:
        messages.error(request, str(e))

    return redirect("excel_import:workspace")
