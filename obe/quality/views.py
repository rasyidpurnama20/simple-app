from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from obe.identity.services import can
from obe.quality.models import (
    AcademicFeedback,
    PortfolioSnapshot,
    QualityFinding,
    QualityReport,
)
from obe.quality.serializers import AcademicFeedbackInputSerializer
from obe.quality.services import feedback_payload_for, submit_academic_feedback


class PortfolioDetailView(APIView):
    def get(self, request, public_id):
        portfolio = get_object_or_404(PortfolioSnapshot, public_id=public_id)
        owner_id = (
            portfolio.scope_id
            if portfolio.portfolio_type == PortfolioSnapshot.PortfolioType.STUDENT
            else ""
        )
        allowed = can(
            request.user,
            "portfolio.view",
            scope_type=portfolio.portfolio_type,
            scope_id=portfolio.scope_id,
            owner_id=owner_id,
        ) or any(
            can(
                request.user,
                action,
                scope_type=portfolio.portfolio_type,
                scope_id=portfolio.scope_id,
            )
            for action in ("portfolio.review", "portfolio.approve", "portfolio.publish")
        )
        if not allowed:
            raise PermissionDenied("Akses portfolio ditolak")
        return Response(
            {
                "schema_version": "obe-portfolio/1",
                "public_id": str(portfolio.public_id),
                "portfolio_type": portfolio.portfolio_type,
                "scope_id": portfolio.scope_id,
                "period": portfolio.period,
                "version": portfolio.version,
                "status": portfolio.status,
                "sections": portfolio.sections,
                "source_versions": portfolio.source_versions,
                "evidence_manifest_ids": portfolio.evidence_manifest_ids,
                "incomplete_sections": portfolio.incomplete_sections,
                "package_checksum": portfolio.package_checksum,
            }
        )


class QualityFindingListView(APIView):
    def get(self, request):
        if not can(request.user, "quality.view"):
            raise PermissionDenied("Akses finding mutu ditolak")
        rows = QualityFinding.objects.select_related("standard").order_by("scope", "standard__code")
        return Response(
            {
                "schema_version": "obe-provus/1",
                "data": [
                    {
                        "source_id": row.source_id,
                        "standard": row.standard.code,
                        "scope": row.scope,
                        "actual": str(row.actual),
                        "target": str(row.target),
                        "gap": str(row.gap),
                        "classification": row.classification,
                        "denominator": row.denominator,
                        "coverage": str(row.coverage),
                        "confidence": row.confidence,
                        "status": row.status,
                        "reason_codes": row.reason_codes,
                    }
                    for row in rows
                ],
            }
        )


class QualityReportDetailView(APIView):
    def get(self, request, public_id):
        report = get_object_or_404(QualityReport, public_id=public_id)
        if report.generated_by_id != request.user.pk and not can(
            request.user,
            "quality.view",
            scope_type=report.scope_type,
            scope_id=report.scope_id,
        ):
            raise PermissionDenied("Akses laporan mutu ditolak")
        return Response(
            {
                "schema_version": "obe-quality-report/1",
                "public_id": str(report.public_id),
                "period": report.period,
                "scope": {"type": report.scope_type, "id": report.scope_id},
                "version": report.version,
                "evaluation_type": report.evaluation_type,
                "status": report.status,
                "sections": report.sections,
                "source_versions": report.source_versions,
                "missing_sections": report.missing_sections,
                "package_checksum": report.package_checksum,
                "approval_history": report.approval_history,
            }
        )


class AcademicFeedbackCollectionView(APIView):
    def post(self, request):
        data = AcademicFeedbackInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        row = submit_academic_feedback(reporter=request.user, **data.validated_data)
        return Response(
            {
                "schema_version": "obe-feedback/1",
                "public_id": str(row.public_id),
                "status": row.status,
                "anonymous": row.anonymous,
            },
            status=201,
        )


class AcademicFeedbackDetailView(APIView):
    def get(self, request, public_id):
        row = get_object_or_404(AcademicFeedback, public_id=public_id)
        return Response(
            {"schema_version": "obe-feedback/1", **feedback_payload_for(row, user=request.user)}
        )
