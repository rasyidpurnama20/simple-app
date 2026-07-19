import hashlib
import logging
import time
import uuid
from pathlib import Path

from django.conf import settings
from django.db import connection
from django.http import JsonResponse

from obe.shared.telemetry import (
    record_http,
    record_query,
    reset_correlation_id,
    safe_attributes,
    set_correlation_id,
    span,
)

logger = logging.getLogger(__name__)


class MaintenanceModeMiddleware:
    ALLOWED_PATHS = {"/healthz/"}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        maintenance_file = settings.OBE_MAINTENANCE_FILE
        maintenance_enabled = settings.OBE_MAINTENANCE_MODE or (
            maintenance_file and Path(maintenance_file).is_file()
        )
        if maintenance_enabled and request.path not in self.ALLOWED_PATHS:
            response = JsonResponse({"status": "maintenance"}, status=503)
            response["Retry-After"] = "300"
            return response
        return self.get_response(request)


class QueryCounter:
    def __init__(self):
        self.count = 0

    def __call__(self, execute, sql, params, many, context):
        self.count += 1
        started = time.monotonic()
        try:
            return execute(sql, params, many, context)
        finally:
            duration_ms = (time.monotonic() - started) * 1000
            record_query(
                duration=duration_ms / 1_000,
                slow=duration_ms >= settings.OBE_SLOW_QUERY_MS,
            )
            if duration_ms >= settings.OBE_SLOW_QUERY_MS:
                normalized = " ".join(sql.split()).encode()
                logger.warning(
                    "Slow query duration_ms=%.2f fingerprint=%s",
                    duration_ms,
                    hashlib.sha256(normalized).hexdigest()[:16],
                )


class QueryBudgetMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        counter = QueryCounter()
        with connection.execute_wrapper(counter):
            response = self.get_response(request)
        response["X-Query-Count"] = str(counter.count)
        if counter.count > settings.OBE_QUERY_BUDGET:
            logger.warning(
                "Query budget exceeded path=%s count=%d budget=%d",
                request.path,
                counter.count,
                settings.OBE_QUERY_BUDGET,
            )
        return response


class CorrelationIdMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        raw = request.headers.get("X-Correlation-ID")
        try:
            request.correlation_id = uuid.UUID(raw) if raw else uuid.uuid4()
        except ValueError:
            request.correlation_id = uuid.uuid4()
        token = set_correlation_id(request.correlation_id)
        started = time.monotonic()
        status = 500
        route = "unresolved"
        try:
            with span(
                "obe.http.request",
                {
                    "http.method": request.method,
                    "correlation_id": str(request.correlation_id),
                },
            ) as current_span:
                response = self.get_response(request)
                status = response.status_code
                resolver_match = getattr(request, "resolver_match", None)
                route = getattr(resolver_match, "route", None) or "unresolved"
                if current_span is not None:
                    current_span.set_attributes(
                        safe_attributes({"http.route": route, "http.status_code": status})
                    )
                response["X-Correlation-ID"] = str(request.correlation_id)
                return response
        finally:
            record_http(
                route=route,
                method=request.method,
                status=status,
                duration=max(0.0, time.monotonic() - started),
            )
            reset_correlation_id(token)


class SecurityHeadersMiddleware:
    POLICY = (
        "default-src 'self'; img-src 'self' data:; font-src 'self'; "
        "style-src 'self'; script-src 'self'; connect-src 'self'; "
        "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault("Content-Security-Policy", self.POLICY)
        response.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        return response
