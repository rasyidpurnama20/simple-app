import hashlib
import json

from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from obe.analytics.serializers import AnalyticsFilterSerializer, TraceFilterSerializer
from obe.assessment.selectors import (
    attainment_trace,
    attainment_trace_context,
    semantic_attainment,
)
from obe.identity.services import can
from obe.quality.selectors import attainment_quality_paths


class SemanticAnalyticsView(APIView):
    def get(self, request):
        if not can(request.user, "analytics.view"):
            raise PermissionDenied("Akses analytics ditolak")
        filters = AnalyticsFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        metric = filters.validated_data["metric"]
        data = []
        warnings = []
        reason_codes = []
        if metric == "attainment":
            data = semantic_attainment(
                course=filters.validated_data.get("course", ""),
                outcome=filters.validated_data.get("outcome", ""),
            )
            if filters.validated_data.get("cohort") or filters.validated_data.get("semester"):
                warnings.append("Snapshot v5 saat ini tersedia pada scope program/mata kuliah")
                reason_codes.append("FILTER_SCOPE_NOT_AVAILABLE")
        if not data:
            warnings.append("Belum ada data pilot")
            reason_codes.append("EMPTY_DATASET")
        actual_series = [row["actual"] for row in data]
        target_series = [row["target"] for row in data]
        payload = {
            "schema_version": "1.0",
            "metric_version": "1.0",
            "rule_version": "CURRENT-AABBC/1",
            "filters": filters.validated_data,
            "cohort": filters.validated_data.get("cohort"),
            "source_versions": {
                "curriculum": 1,
                "assessment": 1,
                "dataset": "5.0.0" if data else None,
            },
            "generated_at": timezone.now().isoformat(),
            "privacy_scope": "program-aggregate" if data else "self",
            "denominator": max((row["denominator"] for row in data), default=0),
            "missing_count": sum(row["actual"] is None for row in data),
            "warnings": warnings,
            "reason_codes": reason_codes,
            "units": "percent",
            "dimensions": ["outcome"],
            "series": [
                {"name": "Aktual", "data": actual_series},
                {"name": "Target", "data": target_series},
            ],
            "data": data,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        etag = hashlib.sha256(canonical).hexdigest()
        response = Response(payload)
        response["ETag"] = f'"{etag}"'
        response["Cache-Control"] = "private, max-age=60"
        return response


class TraceabilityView(APIView):
    def get(self, request, snapshot_id):
        if not can(request.user, "trace.view"):
            raise PermissionDenied("Akses traceability ditolak")
        filters = TraceFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        context = attainment_trace_context(snapshot_id)
        quality_paths = attainment_quality_paths(**context)
        payload = attainment_trace(
            snapshot_id,
            direction=filters.validated_data["direction"],
            start=filters.validated_data.get("start", ""),
            downstream_paths=quality_paths or None,
        )
        payload["schema_version"] = "obe-trace/1"
        payload["generated_at"] = timezone.now().isoformat()
        return Response(payload)
