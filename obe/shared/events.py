from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from django.db import transaction
from django.utils import timezone

from obe.shared.models import ConsumerCursor, InboxEvent, OutboxEvent

EVENT_TYPE_PATTERN = re.compile(r"^[a-z][a-z0-9_-]*(?:\.[a-z][a-z0-9_-]*)+$")
SCHEMA_PATTERN = re.compile(r"^[1-9][0-9]*\.[0-9]+$")
CONSUMER_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{1,79}$")
SUPPORTED_EVENT_SCHEMAS = frozenset({"1.0", "1.1"})
DEFAULT_CONSUMERS = ("cache", "analytics")
MAX_EVENT_PAYLOAD_BYTES = 128 * 1024


@dataclass(frozen=True)
class ConsumeResult:
    status: str
    detail: str
    result_hash: str = ""


@dataclass(frozen=True)
class PublishResult:
    published: int = 0
    retried: int = 0
    dead: int = 0

    def __add__(self, other: PublishResult) -> PublishResult:
        return PublishResult(
            self.published + other.published,
            self.retried + other.retried,
            self.dead + other.dead,
        )


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _error_fingerprint(exc: BaseException) -> str:
    digest = hashlib.sha256(type(exc).__name__.encode()).hexdigest()[:16]
    return f"{type(exc).__name__}:{digest}"


def validate_event_fields(
    *,
    event_type: str,
    aggregate_id: str,
    aggregate_version: int,
    payload_schema: str,
    payload: dict[str, Any],
    consumers: Iterable[str],
) -> tuple[str, ...]:
    if not EVENT_TYPE_PATTERN.fullmatch(event_type):
        raise ValueError("event_type wajib memakai namespace lowercase")
    if not aggregate_id or len(aggregate_id) > 80:
        raise ValueError("aggregate_id tidak valid")
    if aggregate_version < 1:
        raise ValueError("aggregate_version minimal 1")
    if payload_schema not in SUPPORTED_EVENT_SCHEMAS:
        raise ValueError("payload_schema tidak didukung publisher")
    if len(_canonical(payload)) > MAX_EVENT_PAYLOAD_BYTES:
        raise ValueError("Payload event melebihi 128 KiB")
    normalized = tuple(dict.fromkeys(consumers))
    if not normalized or any(not CONSUMER_PATTERN.fullmatch(item) for item in normalized):
        raise ValueError("Daftar consumer event tidak valid")
    return normalized


def create_outbox_event(
    *,
    event_type: str,
    aggregate_id: str,
    aggregate_version: int,
    actor_id: str,
    correlation_id: uuid.UUID,
    payload: dict[str, Any],
    payload_schema: str = "1.0",
    sensitivity: str = "internal",
    consumers: Iterable[str] = DEFAULT_CONSUMERS,
) -> OutboxEvent:
    normalized = validate_event_fields(
        event_type=event_type,
        aggregate_id=aggregate_id,
        aggregate_version=aggregate_version,
        payload_schema=payload_schema,
        payload=payload,
        consumers=consumers,
    )
    return OutboxEvent.objects.create(
        event_type=event_type,
        aggregate_id=aggregate_id,
        aggregate_version=aggregate_version,
        actor_id=actor_id,
        correlation_id=correlation_id,
        payload_schema=payload_schema,
        payload=payload,
        sensitivity=sensitivity,
        consumers=list(normalized),
    )


def event_envelope(event: OutboxEvent) -> dict[str, Any]:
    return {
        "event_id": str(event.event_id),
        "event_type": event.event_type,
        "aggregate_id": event.aggregate_id,
        "version": event.aggregate_version,
        "occurred_at": event.occurred_at.isoformat(),
        "actor": event.actor_id,
        "correlation_id": str(event.correlation_id),
        "payload_schema": event.payload_schema,
        "payload": event.payload,
        "sensitivity": event.sensitivity,
    }


def recover_stale_outbox(*, stale_after_seconds: int = 120) -> int:
    cutoff = timezone.now() - timedelta(seconds=stale_after_seconds)
    return OutboxEvent.objects.filter(
        status=OutboxEvent.Status.PUBLISHING,
        locked_at__lt=cutoff,
        published_at__isnull=True,
    ).update(
        status=OutboxEvent.Status.PENDING,
        locked_at=None,
        next_attempt_at=timezone.now(),
    )


def publish_outbox_batch(
    sender: Callable[[dict[str, Any], tuple[str, ...]], None],
    *,
    batch_size: int = 100,
    max_attempts: int = 5,
) -> PublishResult:
    now = timezone.now()
    event_ids = list(
        OutboxEvent.objects.filter(
            status=OutboxEvent.Status.PENDING,
            published_at__isnull=True,
            next_attempt_at__lte=now,
            attempts__lt=max_attempts,
        )
        .order_by("occurred_at")
        .values_list("event_id", flat=True)[:batch_size]
    )
    result = PublishResult()
    for event_id in event_ids:
        with transaction.atomic():
            event = OutboxEvent.objects.select_for_update().get(event_id=event_id)
            if event.status != OutboxEvent.Status.PENDING or event.next_attempt_at > timezone.now():
                continue
            event.status = OutboxEvent.Status.PUBLISHING
            event.locked_at = timezone.now()
            event.attempts += 1
            event.save(update_fields=["status", "locked_at", "attempts"])
            envelope = event_envelope(event)
            consumers = tuple(event.consumers)
        try:
            sender(envelope, consumers)
        except Exception as exc:
            with transaction.atomic():
                event = OutboxEvent.objects.select_for_update().get(event_id=event_id)
                event.last_error = _error_fingerprint(exc)
                event.locked_at = None
                if event.attempts >= max_attempts:
                    event.status = OutboxEvent.Status.DEAD
                    event.save(update_fields=["status", "last_error", "locked_at"])
                    result += PublishResult(dead=1)
                else:
                    delay = min(300, 2 ** max(0, event.attempts - 1))
                    event.status = OutboxEvent.Status.PENDING
                    event.next_attempt_at = timezone.now() + timedelta(seconds=delay)
                    event.save(
                        update_fields=["status", "next_attempt_at", "last_error", "locked_at"]
                    )
                    result += PublishResult(retried=1)
            continue
        with transaction.atomic():
            event = OutboxEvent.objects.select_for_update().get(event_id=event_id)
            event.status = OutboxEvent.Status.PUBLISHED
            event.published_at = timezone.now()
            event.locked_at = None
            event.last_error = ""
            event.save(update_fields=["status", "published_at", "locked_at", "last_error"])
        result += PublishResult(published=1)
    return result


def _validated_envelope(envelope: dict[str, Any]) -> dict[str, Any]:
    required = {
        "event_id",
        "event_type",
        "aggregate_id",
        "version",
        "occurred_at",
        "actor",
        "correlation_id",
        "payload_schema",
        "payload",
        "sensitivity",
    }
    if set(envelope) != required:
        raise ValueError("Envelope event tidak lengkap atau memiliki field asing")
    uuid.UUID(str(envelope["event_id"]))
    uuid.UUID(str(envelope["correlation_id"]))
    datetime.fromisoformat(str(envelope["occurred_at"]).replace("Z", "+00:00"))
    if not SCHEMA_PATTERN.fullmatch(str(envelope["payload_schema"])):
        raise ValueError("Versi schema event tidak valid")
    if len(str(envelope["actor"])) > 64:
        raise ValueError("Actor event tidak valid")
    if envelope["sensitivity"] not in OutboxEvent.Sensitivity.values:
        raise ValueError("Sensitivity event tidak valid")
    validate_event_fields(
        event_type=str(envelope["event_type"]),
        aggregate_id=str(envelope["aggregate_id"]),
        aggregate_version=int(envelope["version"]),
        payload_schema="1.0",
        payload=dict(envelope["payload"]),
        consumers=("validation",),
    )
    return envelope


def consume_event(
    envelope: dict[str, Any],
    *,
    consumer: str,
    handler: Callable[[dict[str, Any]], Any],
    supported_schemas: frozenset[str] = SUPPORTED_EVENT_SCHEMAS,
) -> ConsumeResult:
    if not CONSUMER_PATTERN.fullmatch(consumer):
        raise ValueError("Nama consumer tidak valid")
    validated = _validated_envelope(envelope)
    event_id = uuid.UUID(str(validated["event_id"]))
    correlation_id = uuid.UUID(str(validated["correlation_id"]))
    version = int(validated["version"])
    metadata = {
        "event_type": str(validated["event_type"]),
        "aggregate_id": str(validated["aggregate_id"]),
        "aggregate_version": version,
        "payload_schema": str(validated["payload_schema"]),
        "correlation_id": correlation_id,
    }
    with transaction.atomic():
        inbox, created = InboxEvent.objects.select_for_update().get_or_create(
            consumer=consumer,
            event_id=event_id,
            defaults={**metadata, "status": InboxEvent.Status.PROCESSING},
        )
        if not created:
            if inbox.status != InboxEvent.Status.FAILED:
                return ConsumeResult("duplicate", "event_id telah diproses", inbox.result_hash)
            inbox.status = InboxEvent.Status.PROCESSING
            inbox.detail = ""
            inbox.save(update_fields=["status", "detail"])
        cursor, _ = ConsumerCursor.objects.select_for_update().get_or_create(
            consumer=consumer,
            event_type=metadata["event_type"],
            aggregate_id=metadata["aggregate_id"],
        )
        if metadata["payload_schema"] not in supported_schemas:
            inbox.status = InboxEvent.Status.REJECTED
            inbox.detail = "schema tidak didukung"
            inbox.save(update_fields=["status", "detail"])
            return ConsumeResult("rejected", inbox.detail)
        if version <= cursor.last_version:
            inbox.status = InboxEvent.Status.REJECTED
            inbox.detail = "event lama atau versi duplikat"
            inbox.save(update_fields=["status", "detail"])
            return ConsumeResult("rejected", inbox.detail)
        if version != cursor.last_version + 1:
            inbox.status = InboxEvent.Status.REJECTED
            inbox.detail = "event di luar urutan"
            inbox.save(update_fields=["status", "detail"])
            return ConsumeResult("rejected", inbox.detail)
        try:
            with transaction.atomic():
                output = handler(validated)
        except Exception as exc:
            inbox.status = InboxEvent.Status.FAILED
            inbox.detail = _error_fingerprint(exc)
            inbox.save(update_fields=["status", "detail"])
            return ConsumeResult("failed", inbox.detail)
        result_hash = _fingerprint(output)
        inbox.status = InboxEvent.Status.PROCESSED
        inbox.detail = "processed"
        inbox.result_hash = result_hash
        inbox.save(update_fields=["status", "detail", "result_hash"])
        cursor.last_version = version
        cursor.last_event_id = event_id
        cursor.save(update_fields=["last_version", "last_event_id", "updated_at"])
        return ConsumeResult("processed", "processed", result_hash)
