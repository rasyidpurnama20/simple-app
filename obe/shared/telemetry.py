from __future__ import annotations

import logging
import re
import uuid
from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Any

from django.conf import settings

SLO_TARGETS = {
    "core_read_p95_seconds": 2.5,
    "error_ratio": 0.01,
    "exam_autosave_p95_seconds": 1.5,
    "pilot_availability_ratio": 0.995,
}
SENSITIVE_ATTRIBUTE = re.compile(
    r"(?i)(name|nim|student|grade|score|answer|token|prompt|authorization|cookie|"
    r"file|path|db\.statement|query\.text|request\.body|response\.body)"
)
ALLOWED_STRING_ATTRIBUTES = {
    "classification",
    "correlation_id",
    "environment",
    "event_type",
    "http.method",
    "http.route",
    "job.queue",
    "job.status",
    "model.alias",
    "outcome",
    "service.name",
    "task.name",
}

_correlation_id: ContextVar[str] = ContextVar("obe_correlation_id", default="")
_configured = False
_tracer = None
_instruments: dict[str, Any] = {}
_providers: list[Any] = []


def set_correlation_id(value: uuid.UUID | str) -> Token:
    return _correlation_id.set(str(value))


def reset_correlation_id(token: Token) -> None:
    _correlation_id.reset(token)


def current_correlation_id() -> str:
    return _correlation_id.get()


class CorrelationContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = current_correlation_id() or "-"
        return True


def safe_attributes(attributes: dict[str, Any] | None) -> dict[str, str | int | float | bool]:
    safe: dict[str, str | int | float | bool] = {}
    for key, value in (attributes or {}).items():
        if SENSITIVE_ATTRIBUTE.search(key):
            continue
        if isinstance(value, bool | int | float):
            safe[key] = value
        elif key in ALLOWED_STRING_ATTRIBUTES:
            safe[key] = str(value)[:160]
    return safe


def configure_telemetry() -> bool:
    global _configured, _tracer
    if _configured or not settings.OBE_TELEMETRY_ENABLED:
        return _configured

    from opentelemetry import metrics, trace
    from opentelemetry._logs import set_logger_provider
    from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.celery import CeleryInstrumentor
    from opentelemetry.instrumentation.django import DjangoInstrumentor
    from opentelemetry.instrumentation.psycopg import PsycopgInstrumentor
    from opentelemetry.instrumentation.redis import RedisInstrumentor
    from opentelemetry.instrumentation.urllib import URLLibInstrumentor
    from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    endpoint = settings.OTEL_EXPORTER_OTLP_ENDPOINT.rstrip("/")
    resource = Resource.create(
        {
            "service.name": settings.OTEL_SERVICE_NAME,
            "service.version": settings.OBE_RELEASE,
            "deployment.environment.name": settings.OBE_ENV,
        }
    )
    trace_provider = TracerProvider(resource=resource)
    trace_provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces"))
    )
    trace.set_tracer_provider(trace_provider)
    _tracer = trace.get_tracer("obe.apps")

    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=f"{endpoint}/v1/metrics"),
        export_interval_millis=settings.OTEL_METRIC_EXPORT_INTERVAL_MS,
    )
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)
    meter = metrics.get_meter("obe.apps")
    _instruments.update(
        {
            "http_count": meter.create_counter("obe.http.requests"),
            "http_duration": meter.create_histogram("obe.http.duration", unit="s"),
            "db_query_count": meter.create_counter("obe.db.queries"),
            "db_query_duration": meter.create_histogram("obe.db.query.duration", unit="s"),
            "task_count": meter.create_counter("obe.task.executions"),
            "task_duration": meter.create_histogram("obe.task.duration", unit="s"),
            "file_access": meter.create_counter("obe.file.access"),
            "ai_tokens": meter.create_counter("obe.ai.tokens"),
            "ai_duration": meter.create_histogram("obe.ai.duration", unit="s"),
            "notification_count": meter.create_counter("obe.notification.deliveries"),
            "edge_sync": meter.create_gauge("obe.exam_edge.last_sync_timestamp", unit="s"),
            "queue_depth": meter.create_gauge("obe.queue.depth"),
            "cache_hit_ratio": meter.create_gauge("obe.cache.hit_ratio"),
            "db_pool_in_use": meter.create_gauge("obe.db.pool.in_use"),
            "db_pool_limit": meter.create_gauge("obe.db.pool.limit"),
            "backup_success": meter.create_gauge("obe.backup.last_success_timestamp", unit="s"),
            "ai_circuit": meter.create_gauge("obe.ai.circuit_open"),
        }
    )

    logger_provider = LoggerProvider(resource=resource)
    logger_provider.add_log_record_processor(
        BatchLogRecordProcessor(OTLPLogExporter(endpoint=f"{endpoint}/v1/logs"))
    )
    set_logger_provider(logger_provider)
    otlp_handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)
    from obe.shared.redaction import SecretRedactionFilter

    otlp_handler.addFilter(SecretRedactionFilter())
    logging.getLogger().addHandler(otlp_handler)
    _providers.extend([trace_provider, meter_provider, logger_provider])

    DjangoInstrumentor().instrument()
    CeleryInstrumentor().instrument(use_span_links=True)
    PsycopgInstrumentor().instrument()
    RedisInstrumentor().instrument()
    URLLibInstrumentor().instrument()
    _configured = True
    return True


def shutdown_telemetry() -> None:
    for provider in reversed(_providers):
        provider.shutdown()
    _providers.clear()


@contextmanager
def span(name: str, attributes: dict[str, Any] | None = None):
    if _tracer is None:
        yield None
        return
    with _tracer.start_as_current_span(name, attributes=safe_attributes(attributes)) as current:
        yield current


def _record(name: str, value: float | int, attributes: dict[str, Any] | None = None) -> None:
    instrument = _instruments.get(name)
    if instrument is None:
        return
    instrument.record(value, safe_attributes(attributes))


def _add(name: str, value: int, attributes: dict[str, Any] | None = None) -> None:
    instrument = _instruments.get(name)
    if instrument is None:
        return
    instrument.add(value, safe_attributes(attributes))


def record_http(*, route: str, method: str, status: int, duration: float) -> None:
    attrs = {
        "http.route": route,
        "http.method": method,
        "http.status_code": status,
        "correlation_id": current_correlation_id(),
    }
    _add("http_count", 1, attrs)
    _record("http_duration", duration, attrs)


def record_query(*, duration: float, slow: bool) -> None:
    attrs = {"outcome": "slow" if slow else "ok", "correlation_id": current_correlation_id()}
    _add("db_query_count", 1, attrs)
    _record("db_query_duration", duration, attrs)


def record_task(*, task_name: str, queue: str, outcome: str, duration: float) -> None:
    attrs = {"task.name": task_name, "job.queue": queue, "outcome": outcome}
    _add("task_count", 1, attrs)
    _record("task_duration", duration, attrs)


def record_file_access(*, classification: str, outcome: str) -> None:
    _add("file_access", 1, {"outcome": outcome, "classification": classification})


def record_ai(*, model_alias: str, tokens: int, outcome: str, duration: float) -> None:
    attrs = {"model.alias": model_alias, "outcome": outcome}
    _add("ai_tokens", max(0, tokens), attrs)
    _record("ai_duration", duration, attrs)


def record_notification(*, outcome: str, count: int = 1) -> None:
    _add("notification_count", max(0, count), {"outcome": outcome})


def set_operational_gauge(name: str, value: float | int, **attributes: Any) -> None:
    instrument = _instruments.get(name)
    if instrument is not None:
        instrument.set(value, safe_attributes(attributes))
