from __future__ import annotations

from pathlib import Path
from typing import Any

from celery import current_app, shared_task
from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.db.models import Count

from obe.shared.audit import purge_expired_sensitive_payloads
from obe.shared.events import consume_event, publish_outbox_batch, recover_stale_outbox
from obe.shared.jobs import create_job, reconcile_stale_jobs
from obe.shared.models import JobExecution
from obe.shared.telemetry import set_operational_gauge

CONSUMER_QUEUES = {
    "cache": "interactive",
    "analytics": "reports",
    "tasks": "academic-critical",
    "notifications": "notifications",
    "sync": "sync",
}


def _send_event(envelope: dict[str, Any], consumers: tuple[str, ...]) -> None:
    for consumer in consumers:
        current_app.send_task(
            "obe.shared.tasks.consume_domain_event",
            kwargs={"consumer": consumer, "envelope": envelope},
            queue=CONSUMER_QUEUES.get(consumer, "academic-critical"),
            headers={
                "correlation_id": envelope["correlation_id"],
                "event_id": envelope["event_id"],
            },
        )


@shared_task(bind=True)
def publish_outbox(self, batch_size: int = 100) -> dict[str, int]:
    result = publish_outbox_batch(
        _send_event,
        batch_size=batch_size,
        max_attempts=settings.OBE_OUTBOX_MAX_ATTEMPTS,
    )
    return {"published": result.published, "retried": result.retried, "dead": result.dead}


def _consumer_handler(consumer: str, envelope: dict[str, Any]) -> dict[str, Any]:
    event_id = envelope["event_id"]
    if consumer == "cache":
        cache.delete(f"aggregate:{envelope['event_type']}:{envelope['aggregate_id']}")
        return {"invalidated": True}
    queue = CONSUMER_QUEUES.get(consumer)
    if queue is None:
        raise ValueError("Consumer domain event tidak didukung")
    job, created = create_job(
        task_name=f"domain-event.{consumer}",
        queue=queue,
        idempotency_key=f"event:{event_id}:{consumer}",
        payload={
            "event_id": event_id,
            "event_type": envelope["event_type"],
            "aggregate_id": envelope["aggregate_id"],
            "version": envelope["version"],
        },
    )
    return {"job_id": str(job.id), "created": created}


@shared_task(bind=True)
def consume_domain_event(self, *, consumer: str, envelope: dict[str, Any]) -> dict[str, str]:
    result = consume_event(
        envelope,
        consumer=consumer,
        handler=lambda event: _consumer_handler(consumer, event),
    )
    return {"status": result.status, "detail": result.detail, "result_hash": result.result_hash}


@shared_task
def reconcile_stale_work() -> dict[str, int]:
    recovered_outbox = recover_stale_outbox()
    requeued_jobs, cancelled_jobs = reconcile_stale_jobs()
    return {
        "recovered_outbox": recovered_outbox,
        "requeued_jobs": requeued_jobs,
        "cancelled_jobs": cancelled_jobs,
    }


@shared_task
def enforce_audit_retention() -> dict[str, int]:
    return {"purged_sensitive_payloads": purge_expired_sensitive_payloads()}


@shared_task
def collect_operational_metrics() -> dict[str, int | float]:
    active_connections = 1
    if connection.vendor == "postgresql":
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT count(*) FROM pg_stat_activity WHERE application_name = %s",
                [connection.settings_dict.get("OPTIONS", {}).get("application_name", "obe-apps")],
            )
            active_connections = int(cursor.fetchone()[0])
    set_operational_gauge("db_pool_in_use", active_connections)
    set_operational_gauge("db_pool_limit", settings.OBE_DB_CONNECTION_LIMIT)
    queued = {
        row["queue"]: row["total"]
        for row in JobExecution.objects.filter(status=JobExecution.Status.QUEUED)
        .values("queue")
        .annotate(total=Count("id"))
    }
    for queue, depth in queued.items():
        set_operational_gauge("queue_depth", depth, **{"job.queue": queue})
    backup_timestamp = 0.0
    if settings.OBE_BACKUP_SUCCESS_FILE:
        path = Path(settings.OBE_BACKUP_SUCCESS_FILE)
        if path.is_file():
            backup_timestamp = path.stat().st_mtime
    set_operational_gauge("backup_success", backup_timestamp)
    return {
        "active_connections": active_connections,
        "connection_limit": settings.OBE_DB_CONNECTION_LIMIT,
        "queued_jobs": sum(queued.values()),
        "backup_timestamp": backup_timestamp,
    }
