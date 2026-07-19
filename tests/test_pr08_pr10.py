from __future__ import annotations

import json
import uuid
from datetime import timedelta
from pathlib import Path

import pytest
from celery.signals import before_task_publish
from django.core.cache import cache
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from obe.shared.ephemeral import (
    allow_rate,
    ephemeral_lock,
    get_short_state,
    put_short_state,
)
from obe.shared.events import (
    consume_event,
    create_outbox_event,
    event_envelope,
    publish_outbox_batch,
    recover_stale_outbox,
)
from obe.shared.jobs import create_job, execute_job, reconcile_stale_jobs, request_cancellation
from obe.shared.models import ConsumerCursor, InboxEvent, JobExecution, OutboxEvent
from obe.shared.queueing import (
    DEAD_LETTER_QUEUE,
    QUEUE_POLICIES,
    build_task_queues,
    guard_publish_payload,
    task_routes,
    validate_task_payload,
)
from obe.shared.telemetry import SLO_TARGETS, safe_attributes

ROOT = Path(__file__).resolve().parents[1]


def test_pr08_queue_contracts_are_bounded_and_isolated():
    required = {
        "interactive",
        "academic-critical",
        "ai",
        "reports",
        "imports",
        "notifications",
        "sync",
        "batch",
        "maintenance",
    }
    assert set(QUEUE_POLICIES) == required
    queues = {queue.name: queue for queue in build_task_queues()}
    assert set(queues) == required | {DEAD_LETTER_QUEUE}
    for name in required:
        arguments = queues[name].queue_arguments
        assert arguments["x-max-length"] == QUEUE_POLICIES[name].max_length
        assert arguments["x-message-ttl"] == QUEUE_POLICIES[name].message_ttl_ms
        assert arguments["x-dead-letter-routing-key"] == DEAD_LETTER_QUEUE
    routes = task_routes()
    assert routes["obe.ai.*"]["queue"] == "ai"
    assert routes["obe.integration.*"]["queue"] == "imports"
    assert routes["obe.secure_exam.*"]["queue"] == "sync"


def test_task_payload_and_correlation_guard_reject_oversize(settings):
    limit = QUEUE_POLICIES["interactive"].max_payload_bytes
    assert validate_task_payload({"value": "ok"}, "interactive") > 0
    with pytest.raises(ValueError, match="Payload task"):
        validate_task_payload({"value": "x" * limit}, "interactive")
    headers = {}
    before_task_publish.send(
        sender="tests.task",
        body={"value": "ok"},
        headers=headers,
        routing_key="interactive",
    )
    assert uuid.UUID(headers["correlation_id"])
    assert headers["payload_bytes"] > 0
    settings.OBE_TASK_PAYLOAD_LIMIT_BYTES = 2
    with pytest.raises(ValueError, match="batas global"):
        guard_publish_payload(
            task_name="tests.task",
            args=(),
            kwargs={"value": "too-large"},
            queue="interactive",
            headers={},
            global_limit=2,
        )


def test_valkey_ephemeral_state_rate_limit_and_lock():
    cache.clear()
    put_short_state("wizard", "actor-1", {"step": 2}, ttl=30)
    assert get_short_state("wizard", "actor-1") == {"step": 2}
    assert allow_rate("api", "actor-1", limit=2, window_seconds=60)
    assert allow_rate("api", "actor-1", limit=2, window_seconds=60)
    assert not allow_rate("api", "actor-1", limit=2, window_seconds=60)
    with ephemeral_lock("report", "same-object") as acquired:
        assert acquired
        with ephemeral_lock("report", "same-object") as duplicate:
            assert not duplicate


@pytest.mark.django_db
def test_job_duplicate_delivery_has_zero_duplicate_side_effect():
    job, created = create_job(
        task_name="reports.render",
        queue="reports",
        idempotency_key="report:IF:2026",
        payload={"program": "IF"},
    )
    assert created
    duplicate, created_again = create_job(
        task_name="reports.render",
        queue="reports",
        idempotency_key="report:IF:2026",
        payload={"program": "IF"},
    )
    assert duplicate.id == job.id and not created_again
    effects = []

    def render(progress):
        effects.append("rendered")
        assert progress(50)
        return {"artifact": "report-1"}

    first = execute_job(job.id, generation=1, operation=render)
    second = execute_job(job.id, generation=1, operation=render)
    assert first.status == "succeeded" and second.status == "duplicate"
    assert effects == ["rendered"]
    job.refresh_from_db()
    assert job.progress == 100 and len(job.result_hash) == 64
    with pytest.raises(ValueError, match="payload berbeda"):
        create_job(
            task_name="reports.render",
            queue="reports",
            idempotency_key="report:IF:2026",
            payload={"program": "SI"},
        )


@pytest.mark.django_db
def test_job_cancellation_discards_stale_result_and_stale_lease_requeues():
    job, _ = create_job(
        task_name="imports.sample",
        queue="imports",
        idempotency_key="import:sample:1",
        payload={"dataset": "v5"},
    )

    def cancelled_operation(_progress):
        request_cancellation(job.id)
        return {"rows": 77}

    outcome = execute_job(job.id, generation=1, operation=cancelled_operation)
    assert outcome.status == "stale"
    job.refresh_from_db()
    assert job.status == JobExecution.Status.CANCELLED and job.result == {}

    stale = JobExecution.objects.create(
        task_name="sync.edge",
        queue="sync",
        idempotency_key="sync:stale:1",
        payload_hash="a" * 64,
        status=JobExecution.Status.RUNNING,
        generation=1,
        lease_expires_at=timezone.now() - timedelta(seconds=1),
        expires_at=timezone.now() + timedelta(minutes=5),
    )
    requeued, cancelled = reconcile_stale_jobs()
    stale.refresh_from_db()
    assert (requeued, cancelled) == (1, 0)
    assert stale.status == JobExecution.Status.QUEUED and stale.generation == 2


@pytest.mark.django_db
def test_job_failure_expiry_saturation_and_input_guards():
    with pytest.raises(ValueError, match="Nama task"):
        create_job(task_name="", queue="batch", idempotency_key="invalid", payload={})
    with pytest.raises(ValueError, match="Idempotency"):
        create_job(task_name="batch.run", queue="batch", idempotency_key="", payload={})

    failed, _ = create_job(
        task_name="batch.fail",
        queue="batch",
        idempotency_key="batch:fail",
        payload={},
    )
    outcome = execute_job(
        failed.id,
        generation=1,
        operation=lambda _progress: (_ for _ in ()).throw(OSError("private detail")),
    )
    failed.refresh_from_db()
    assert outcome.status == "failed" and "private detail" not in failed.last_error

    expired, _ = create_job(
        task_name="batch.expired",
        queue="batch",
        idempotency_key="batch:expired",
        payload={},
    )
    JobExecution.objects.filter(pk=expired.pk).update(expires_at=timezone.now())
    assert execute_job(expired.id, generation=1, operation=lambda _progress: {}).status == "expired"

    cancelled, _ = create_job(
        task_name="batch.cancel",
        queue="batch",
        idempotency_key="batch:cancel",
        payload={},
    )
    assert request_cancellation(cancelled.id) == JobExecution.Status.CANCELLED
    assert (
        execute_job(cancelled.id, generation=1, operation=lambda _progress: {}).status
        == "cancelled"
    )

    running, _ = create_job(
        task_name="batch.running",
        queue="batch",
        idempotency_key="batch:running",
        payload={},
    )
    JobExecution.objects.filter(pk=running.pk).update(
        status=JobExecution.Status.RUNNING,
        lease_expires_at=timezone.now() + timedelta(minutes=1),
    )
    assert (
        execute_job(running.id, generation=1, operation=lambda _progress: {}).status == "duplicate"
    )
    assert execute_job(running.id, generation=2, operation=lambda _progress: {}).status == "stale"

    for index in range(QUEUE_POLICIES["maintenance"].max_active_jobs):
        JobExecution.objects.create(
            task_name="maintenance.active",
            queue="maintenance",
            idempotency_key=f"maintenance:active:{index}",
            payload_hash="b" * 64,
            status=JobExecution.Status.RUNNING,
            lease_expires_at=timezone.now() + timedelta(minutes=1),
            expires_at=timezone.now() + timedelta(minutes=5),
        )
    saturated, _ = create_job(
        task_name="maintenance.next",
        queue="maintenance",
        idempotency_key="maintenance:next",
        payload={},
    )
    assert (
        execute_job(saturated.id, generation=1, operation=lambda _progress: {}).status
        == "saturated"
    )


def _new_event(*, version: int = 1, schema: str = "1.0") -> OutboxEvent:
    return create_outbox_event(
        event_type="curriculum.activated",
        aggregate_id="IF-2026",
        aggregate_version=version,
        actor_id="prodi-1",
        correlation_id=uuid.uuid4(),
        payload={"status": "active"},
        payload_schema=schema,
        consumers=("cache",),
    )


@pytest.mark.django_db
def test_outbox_commit_rollback_retry_and_history_retention():
    with pytest.raises(RuntimeError):
        with transaction.atomic():
            _new_event()
            raise RuntimeError("rollback")
    assert not OutboxEvent.objects.exists()

    event = _new_event()
    sent = []
    result = publish_outbox_batch(lambda envelope, consumers: sent.append((envelope, consumers)))
    event.refresh_from_db()
    assert result.published == 1 and event.status == OutboxEvent.Status.PUBLISHED
    assert event.published_at is not None and OutboxEvent.objects.filter(pk=event.pk).exists()
    assert sent[0][0]["event_id"] == str(event.event_id)
    assert sent[0][0]["correlation_id"] == str(event.correlation_id)

    failed = create_outbox_event(
        event_type="assessment.scored",
        aggregate_id="SUB-1",
        aggregate_version=1,
        actor_id="lecturer-1",
        correlation_id=uuid.uuid4(),
        payload={"status": "scored"},
        consumers=("analytics",),
    )

    def unavailable(_envelope, _consumers):
        raise OSError("broker detail must not be stored")

    first = publish_outbox_batch(unavailable, max_attempts=2)
    failed.refresh_from_db()
    assert first.retried == 1 and "broker detail" not in failed.last_error
    failed.next_attempt_at = timezone.now()
    failed.save(update_fields=["next_attempt_at"])
    second = publish_outbox_batch(unavailable, max_attempts=2)
    failed.refresh_from_db()
    assert second.dead == 1 and failed.status == OutboxEvent.Status.DEAD


@pytest.mark.django_db
def test_outbox_validation_and_stale_publisher_recovery():
    with pytest.raises(ValueError, match="namespace"):
        create_outbox_event(
            event_type="InvalidEvent",
            aggregate_id="1",
            aggregate_version=1,
            actor_id="actor",
            correlation_id=uuid.uuid4(),
            payload={},
        )
    with pytest.raises(ValueError, match="128 KiB"):
        create_outbox_event(
            event_type="valid.event",
            aggregate_id="1",
            aggregate_version=1,
            actor_id="actor",
            correlation_id=uuid.uuid4(),
            payload={"value": "x" * (128 * 1024)},
        )
    event = _new_event()
    OutboxEvent.objects.filter(pk=event.pk).update(
        status=OutboxEvent.Status.PUBLISHING,
        locked_at=timezone.now() - timedelta(minutes=5),
    )
    assert recover_stale_outbox(stale_after_seconds=60) == 1
    event.refresh_from_db()
    assert event.status == OutboxEvent.Status.PENDING and event.locked_at is None


@pytest.mark.django_db
def test_inbox_rejects_duplicate_out_of_order_and_unsupported_schema():
    event = _new_event()
    envelope = event_envelope(event)
    effects = []
    first = consume_event(
        envelope,
        consumer="cache",
        handler=lambda item: effects.append(item["event_id"]) or {"ok": True},
    )
    duplicate = consume_event(
        envelope,
        consumer="cache",
        handler=lambda item: effects.append(item["event_id"]) or {"ok": True},
    )
    assert first.status == "processed" and duplicate.status == "duplicate"
    assert effects == [str(event.event_id)]

    out_of_order = event_envelope(_new_event(version=3))
    rejected = consume_event(out_of_order, consumer="analytics", handler=lambda _item: {})
    assert rejected.status == "rejected" and "urutan" in rejected.detail

    schema_v11 = event_envelope(_new_event(schema="1.1"))
    unsupported = consume_event(
        schema_v11,
        consumer="sync",
        handler=lambda _item: {},
        supported_schemas=frozenset({"1.0"}),
    )
    assert unsupported.status == "rejected" and "schema" in unsupported.detail
    assert InboxEvent.objects.filter(status=InboxEvent.Status.REJECTED).count() == 2


@pytest.mark.django_db
def test_failed_consumer_can_restart_without_losing_event():
    envelope = event_envelope(_new_event())
    failed = consume_event(
        envelope,
        consumer="notifications",
        handler=lambda _item: (_ for _ in ()).throw(OSError("temporary")),
    )
    recovered = consume_event(
        envelope,
        consumer="notifications",
        handler=lambda _item: {"created": True},
    )
    assert failed.status == "failed" and recovered.status == "processed"
    cursor = ConsumerCursor.objects.get(consumer="notifications")
    assert cursor.last_version == 1


def test_pr10_slo_redaction_dashboard_and_alert_contracts():
    assert SLO_TARGETS == {
        "core_read_p95_seconds": 2.5,
        "error_ratio": 0.01,
        "exam_autosave_p95_seconds": 1.5,
        "pilot_availability_ratio": 0.995,
    }
    attributes = safe_attributes(
        {
            "correlation_id": str(uuid.uuid4()),
            "http.route": "evidence/<uuid>/",
            "student.number": "24001",
            "grade.raw": 95,
            "exam.answer": "secret",
            "ai.prompt": "private",
            "file.path": "/private/evidence.pdf",
            "http.status_code": 200,
        }
    )
    assert "correlation_id" in attributes and "http.route" in attributes
    assert "http.status_code" in attributes
    assert not {"student.number", "grade.raw", "exam.answer", "ai.prompt", "file.path"} & set(
        attributes
    )

    alerts = (ROOT / "deploy/observability/alerts.yml").read_text(encoding="utf-8")
    for alert in (
        "OBEDiskUsageHigh",
        "OBEQueueSaturated",
        "OBEDBPoolExhausted",
        "OBEBackupFailed",
        "OBEAICircuitOpen",
        "OBEExamEdgeOffline",
    ):
        assert f"alert: {alert}" in alerts
    collector = (ROOT / "deploy/observability/otel.yml").read_text(encoding="utf-8")
    for sensitive_key in ("student.number", "grade.raw", "exam.answer", "ai.prompt", "file.path"):
        assert f"key: {sensitive_key}" in collector
    dashboard = json.loads(
        (ROOT / "deploy/observability/grafana/dashboards/obe-overview.json").read_text(
            encoding="utf-8"
        )
    )
    panel_titles = {panel["title"] for panel in dashboard["panels"]}
    assert {
        "CPU and RAM",
        "Disk",
        "DB pool",
        "Queue depth",
        "Cache hit",
        "AI tokens",
        "Failed jobs",
    } <= panel_titles


@pytest.mark.django_db
def test_specialized_workers_and_core_web_are_decoupled(client, settings):
    compose = (ROOT / "deploy/server/compose.yml").read_text(encoding="utf-8")
    for worker in (
        "worker-ai",
        "worker-reports",
        "worker-imports",
        "worker-notifications",
        "worker-sync",
        "worker-batch",
    ):
        assert f"  {worker}:" in compose
    assert "dead-letter" in (ROOT / "obe/shared/queueing.py").read_text(encoding="utf-8")
    settings.OBE_AI_ENABLED = False
    assert client.get(reverse("healthz")).status_code == 200
    assert client.get(reverse("readyz")).status_code == 200


def test_correlation_id_is_preserved_or_replaced(client):
    requested = uuid.uuid4()
    response = client.get(reverse("healthz"), headers={"X-Correlation-ID": str(requested)})
    assert response["X-Correlation-ID"] == str(requested)
    replaced = client.get(reverse("healthz"), headers={"X-Correlation-ID": "not-a-uuid"})
    assert uuid.UUID(replaced["X-Correlation-ID"]) != requested


@pytest.mark.django_db
def test_domain_event_tasks_and_operational_metrics(monkeypatch, settings, tmp_path):
    from obe.shared import tasks as shared_tasks

    sent = []
    monkeypatch.setattr(
        shared_tasks.current_app,
        "send_task",
        lambda name, **options: sent.append((name, options)),
    )
    event = _new_event()
    result = shared_tasks.publish_outbox.run(batch_size=10)
    assert result == {"published": 1, "retried": 0, "dead": 0}
    assert sent[0][0] == "obe.shared.tasks.consume_domain_event"

    consumed = shared_tasks.consume_domain_event.run(
        consumer="cache",
        envelope=event_envelope(event),
    )
    assert consumed["status"] == "processed"
    with pytest.raises(ValueError, match="tidak didukung"):
        shared_tasks._consumer_handler("unknown", event_envelope(event))

    backup = tmp_path / "backup-success.timestamp"
    backup.touch()
    settings.OBE_BACKUP_SUCCESS_FILE = str(backup)
    metrics = shared_tasks.collect_operational_metrics.run()
    assert metrics["connection_limit"] == settings.OBE_DB_CONNECTION_LIMIT
    assert metrics["backup_timestamp"] > 0
    assert set(shared_tasks.reconcile_stale_work.run()) == {
        "recovered_outbox",
        "requeued_jobs",
        "cancelled_jobs",
    }


def test_zz_telemetry_pipeline_initializes_and_records(monkeypatch, settings):
    from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk._logs.export import LogExportResult
    from opentelemetry.sdk.metrics.export import MetricExportResult
    from opentelemetry.sdk.trace.export import SpanExportResult

    from obe.shared import telemetry

    monkeypatch.setattr(
        OTLPSpanExporter,
        "export",
        lambda *_args, **_kwargs: SpanExportResult.SUCCESS,
    )
    monkeypatch.setattr(
        OTLPMetricExporter,
        "export",
        lambda *_args, **_kwargs: MetricExportResult.SUCCESS,
    )
    monkeypatch.setattr(
        OTLPLogExporter,
        "export",
        lambda *_args, **_kwargs: LogExportResult.SUCCESS,
    )
    settings.OBE_TELEMETRY_ENABLED = True
    settings.OTEL_EXPORTER_OTLP_ENDPOINT = "http://127.0.0.1:4318"
    settings.OTEL_METRIC_EXPORT_INTERVAL_MS = 60_000
    assert telemetry.configure_telemetry()
    token = telemetry.set_correlation_id(uuid.uuid4())
    with telemetry.span("obe.tests", {"student.number": "must-drop", "outcome": "ok"}):
        telemetry.record_http(route="healthz/", method="GET", status=200, duration=0.01)
        telemetry.record_query(duration=0.001, slow=False)
        telemetry.record_task(
            task_name="tests.task", queue="batch", outcome="success", duration=0.1
        )
        telemetry.record_file_access(classification="internal", outcome="success")
        telemetry.record_ai(model_alias="local-small", tokens=3, outcome="success", duration=0.2)
        telemetry.record_notification(outcome="created", count=1)
        telemetry.set_operational_gauge("queue_depth", 2, **{"job.queue": "batch"})
    telemetry.reset_correlation_id(token)
    assert telemetry.configure_telemetry()
    telemetry.shutdown_telemetry()
