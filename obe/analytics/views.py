import hashlib
import json

from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from obe.analytics.serializers import AnalyticsFilterSerializer


class SemanticAnalyticsView(APIView):
    def get(self, request):
        filters = AnalyticsFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        metric = filters.validated_data["metric"]
        payload = {
            "schema_version": "1.0",
            "metric_version": "1.0",
            "rule_version": "CURRENT-AABBC/1",
            "filters": filters.validated_data,
            "cohort": filters.validated_data.get("cohort"),
            "source_versions": {"curriculum": 1, "assessment": 1},
            "generated_at": timezone.now().isoformat(),
            "privacy_scope": "self" if not request.user.is_staff else "program",
            "denominator": 0,
            "missing_count": 0,
            "warnings": ["Belum ada data pilot"],
            "reason_codes": ["EMPTY_DATASET"],
            "units": "percent",
            "dimensions": ["outcome"],
            "series": [{"name": metric, "data": []}],
            "data": [],
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        etag = hashlib.sha256(canonical).hexdigest()
        response = Response(payload)
        response["ETag"] = f'"{etag}"'
        response["Cache-Control"] = "private, max-age=60"
        return response
