from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass
from fnmatch import fnmatchcase
from typing import Any

from celery import Celery, Task
from kombu import Exchange, Queue

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class QueuePolicy:
    max_length: int
    max_payload_bytes: int
    message_ttl_ms: int
    hard_timeout: int
    soft_timeout: int
    max_retries: int
    max_active_jobs: int


QUEUE_POLICIES = {
    "interactive": QueuePolicy(2_000, 64 * 1024, 120_000, 30, 25, 3, 8),
    "academic-critical": QueuePolicy(5_000, 128 * 1024, 900_000, 120, 105, 5, 8),
    "ai": QueuePolicy(200, 64 * 1024, 600_000, 180, 165, 2, 2),
    "reports": QueuePolicy(200, 128 * 1024, 1_800_000, 600, 570, 2, 2),
    "imports": QueuePolicy(100, 256 * 1024, 3_600_000, 900, 870, 2, 1),
    "notifications": QueuePolicy(5_000, 64 * 1024, 900_000, 60, 50, 5, 4),
    "sync": QueuePolicy(1_000, 128 * 1024, 1_800_000, 300, 270, 5, 2),
    "batch": QueuePolicy(500, 128 * 1024, 3_600_000, 900, 870, 3, 2),
    "maintenance": QueuePolicy(100, 64 * 1024, 3_600_000, 600, 570, 3, 1),
}
DEAD_LETTER_QUEUE = "dead-letter"
TASK_EXCHANGE = Exchange("obe.tasks", type="direct", durable=True)
DEAD_LETTER_EXCHANGE = Exchange("obe.dead-letter", type="direct", durable=True)


def build_task_queues() -> tuple[Queue, ...]:
    queues = [
        Queue(
            name,
            TASK_EXCHANGE,
            routing_key=name,
            durable=True,
            queue_arguments={
                "x-max-length": policy.max_length,
                "x-message-ttl": policy.message_ttl_ms,
                "x-overflow": "reject-publish-dlx",
                "x-dead-letter-exchange": DEAD_LETTER_EXCHANGE.name,
                "x-dead-letter-routing-key": DEAD_LETTER_QUEUE,
            },
        )
        for name, policy in QUEUE_POLICIES.items()
    ]
    queues.append(
        Queue(
            DEAD_LETTER_QUEUE,
            DEAD_LETTER_EXCHANGE,
            routing_key=DEAD_LETTER_QUEUE,
            durable=True,
            queue_arguments={"x-max-length": 10_000, "x-overflow": "reject-publish"},
        )
    )
    return tuple(queues)


def task_routes() -> dict[str, dict[str, str]]:
    return {
        "obe.shared.tasks.publish_outbox": {"queue": "academic-critical"},
        "obe.shared.tasks.consume_domain_event": {"queue": "academic-critical"},
        "obe.shared.tasks.reconcile_stale_work": {"queue": "maintenance"},
        "obe.shared.tasks.collect_operational_metrics": {"queue": "maintenance"},
        "obe.academic_lifecycle.tasks.schedule_task_reminders": {"queue": "notifications"},
        "obe.ai.*": {"queue": "ai"},
        "obe.analytics.*": {"queue": "reports"},
        "obe.integration.*": {"queue": "imports"},
        "obe.secure_exam.*": {"queue": "sync"},
        "obe.*.tasks.*": {"queue": "batch"},
    }


def task_annotations() -> dict[str, dict[str, int | bool]]:
    task_policies = {
        "obe.shared.tasks.publish_outbox": "academic-critical",
        "obe.shared.tasks.consume_domain_event": "academic-critical",
        "obe.shared.tasks.reconcile_stale_work": "maintenance",
        "obe.shared.tasks.collect_operational_metrics": "maintenance",
        "obe.academic_lifecycle.tasks.schedule_task_reminders": "notifications",
        "obe.ai.*": "ai",
        "obe.analytics.*": "reports",
        "obe.integration.*": "imports",
        "obe.secure_exam.*": "sync",
        "*": "batch",
    }
    return {
        task_name: {
            "time_limit": policy.hard_timeout,
            "soft_time_limit": policy.soft_timeout,
            "max_retries": policy.max_retries,
            "acks_late": True,
        }
        for task_name, queue in task_policies.items()
        for policy in (QUEUE_POLICIES[queue],)
    }


def payload_size(payload: Any) -> int:
    return len(json.dumps(payload, separators=(",", ":"), default=str).encode())


def validate_task_payload(payload: Any, queue: str) -> int:
    if queue not in QUEUE_POLICIES:
        raise ValueError(f"Antrean tidak dikenal: {queue}")
    size = payload_size(payload)
    if size > QUEUE_POLICIES[queue].max_payload_bytes:
        raise ValueError(f"Payload task melebihi batas antrean {queue}")
    return size


def correlation_id(headers: dict[str, Any] | None = None) -> uuid.UUID:
    raw = (headers or {}).get("correlation_id")
    try:
        return uuid.UUID(str(raw)) if raw else uuid.uuid4()
    except (TypeError, ValueError):
        return uuid.uuid4()


def queue_for_task(task_name: str) -> str:
    for pattern, route in task_routes().items():
        if fnmatchcase(task_name, pattern):
            return route["queue"]
    return "interactive"


def guard_publish_payload(
    *,
    task_name: str,
    args: Any,
    kwargs: Any,
    queue: str | None,
    headers: dict[str, Any] | None,
    global_limit: int,
) -> tuple[str, dict[str, Any]]:
    selected_queue = queue or queue_for_task(task_name)
    prepared_headers = dict(headers or {})
    prepared_headers["correlation_id"] = str(correlation_id(prepared_headers))
    size = validate_task_payload({"args": args or (), "kwargs": kwargs or {}}, selected_queue)
    if size > global_limit:
        raise ValueError("Payload task melebihi batas global")
    prepared_headers["payload_bytes"] = size
    return selected_queue, prepared_headers


class GuardedCelery(Celery):
    def send_task(self, name, args=None, kwargs=None, **options):
        from django.conf import settings

        queue, headers = guard_publish_payload(
            task_name=name,
            args=args,
            kwargs=kwargs,
            queue=options.get("queue"),
            headers=options.get("headers"),
            global_limit=settings.OBE_TASK_PAYLOAD_LIMIT_BYTES,
        )
        options["queue"] = queue
        options["headers"] = headers
        return super().send_task(name, args=args, kwargs=kwargs, **options)


class GuardedTask(Task):
    abstract = True

    def apply_async(self, args=None, kwargs=None, **options):
        from django.conf import settings

        queue, headers = guard_publish_payload(
            task_name=self.name,
            args=args,
            kwargs=kwargs,
            queue=options.get("queue"),
            headers=options.get("headers"),
            global_limit=settings.OBE_TASK_PAYLOAD_LIMIT_BYTES,
        )
        options["queue"] = queue
        options["headers"] = headers
        return super().apply_async(args=args, kwargs=kwargs, **options)


_guards_installed = False


def install_celery_guards() -> None:
    global _guards_installed
    if _guards_installed:
        return
    from celery import current_app
    from celery.signals import before_task_publish, task_failure, task_postrun, task_prerun
    from django.conf import settings

    @before_task_publish.connect(weak=False)
    def guard_publish(sender=None, body=None, headers=None, routing_key=None, **_kwargs):
        headers = headers if headers is not None else {}
        headers["correlation_id"] = str(correlation_id(headers))
        queue = routing_key if routing_key in QUEUE_POLICIES else settings.CELERY_TASK_DEFAULT_QUEUE
        size = validate_task_payload(body, queue)
        headers["payload_bytes"] = size

    @task_failure.connect(weak=False)
    def quarantine_poison(sender=None, task_id=None, exception=None, **_kwargs):
        task_name = getattr(sender, "name", "unknown")
        error_type = type(exception).__name__ if exception else "UnknownError"
        fingerprint = uuid.uuid5(uuid.NAMESPACE_URL, f"{task_name}:{error_type}").hex[:16]
        envelope = {
            "task_id": str(task_id or ""),
            "task_name": task_name,
            "error_fingerprint": fingerprint,
        }
        try:
            with current_app.producer_or_acquire() as producer:
                producer.publish(
                    envelope,
                    exchange=DEAD_LETTER_EXCHANGE,
                    routing_key=DEAD_LETTER_QUEUE,
                    serializer="json",
                    retry=True,
                    retry_policy={"max_retries": 1},
                )
        except Exception:
            logger.exception("Poison-message quarantine failed task=%s", task_name)

    @task_prerun.connect(weak=False)
    def start_task_trace(task_id=None, task=None, **_kwargs):
        from obe.shared.telemetry import set_correlation_id

        request = getattr(task, "request", None)
        if request is None:
            return
        headers = getattr(request, "headers", None) or {}
        request._obe_correlation_token = set_correlation_id(correlation_id(headers))
        request._obe_started_at = time.monotonic()

    @task_postrun.connect(weak=False)
    def finish_task_trace(task_id=None, task=None, state=None, **_kwargs):
        from obe.shared.telemetry import record_task, reset_correlation_id

        request = getattr(task, "request", None)
        if request is None:
            return
        started = getattr(request, "_obe_started_at", time.monotonic())
        delivery = getattr(request, "delivery_info", None) or {}
        record_task(
            task_name=getattr(task, "name", "unknown"),
            queue=str(delivery.get("routing_key", "unknown")),
            outcome=str(state or "unknown").lower(),
            duration=max(0.0, time.monotonic() - started),
        )
        token = getattr(request, "_obe_correlation_token", None)
        if token is not None:
            reset_correlation_id(token)

    _guards_installed = True
