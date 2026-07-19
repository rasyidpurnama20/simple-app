from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from django.db import transaction
from django.utils import timezone

from obe.shared.models import JobExecution
from obe.shared.queueing import QUEUE_POLICIES, validate_task_payload


@dataclass(frozen=True)
class JobOutcome:
    status: str
    result: dict[str, Any]
    detail: str = ""


def _digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def _error_fingerprint(exc: BaseException) -> str:
    digest = hashlib.sha256(type(exc).__name__.encode()).hexdigest()[:16]
    return f"{type(exc).__name__}:{digest}"


def create_job(
    *,
    task_name: str,
    queue: str,
    idempotency_key: str,
    payload: dict[str, Any],
    correlation_id: uuid.UUID | None = None,
    ttl_seconds: int | None = None,
    authorization_snapshot: dict[str, Any] | None = None,
    feature_snapshot: dict[str, Any] | None = None,
) -> tuple[JobExecution, bool]:
    if not task_name or len(task_name) > 180:
        raise ValueError("Nama task tidak valid")
    if not idempotency_key or len(idempotency_key) > 160:
        raise ValueError("Idempotency key tidak valid")
    validate_task_payload(payload, queue)
    payload_hash = _digest(payload)
    policy = QUEUE_POLICIES[queue]
    ttl = ttl_seconds or max(60, policy.message_ttl_ms // 1_000)
    with transaction.atomic():
        job, created = JobExecution.objects.get_or_create(
            idempotency_key=idempotency_key,
            defaults={
                "task_name": task_name,
                "queue": queue,
                "correlation_id": correlation_id or uuid.uuid4(),
                "payload_hash": payload_hash,
                "authorization_snapshot": authorization_snapshot or {},
                "feature_snapshot": feature_snapshot or {},
                "expires_at": timezone.now() + timedelta(seconds=ttl),
            },
        )
        if not created and (
            job.payload_hash != payload_hash or job.task_name != task_name or job.queue != queue
        ):
            raise ValueError("Idempotency key telah dipakai untuk task atau payload berbeda")
    return job, created


def _snapshots_valid(job: JobExecution) -> bool:
    if job.authorization_snapshot:
        from obe.identity.services import validate_permission_snapshot

        if not validate_permission_snapshot(job.authorization_snapshot):
            return False
    if job.feature_snapshot:
        from obe.shared.feature_flags import validate_flag_snapshot

        if not validate_flag_snapshot(job.feature_snapshot):
            return False
    return True


def update_progress(job_id: uuid.UUID, *, generation: int, progress: int) -> bool:
    if not 0 <= progress <= 99:
        raise ValueError("Progress task harus 0–99 sebelum selesai")
    updated = JobExecution.objects.filter(
        id=job_id,
        generation=generation,
        status=JobExecution.Status.RUNNING,
        cancel_requested=False,
    ).update(progress=progress)
    return updated == 1


def request_cancellation(job_id: uuid.UUID) -> str:
    with transaction.atomic():
        job = JobExecution.objects.select_for_update().get(id=job_id)
        if job.status in {JobExecution.Status.SUCCEEDED, JobExecution.Status.CANCELLED}:
            return job.status
        job.cancel_requested = True
        job.generation += 1
        fields = ["cancel_requested", "generation", "updated_at"]
        if job.status == JobExecution.Status.QUEUED:
            job.status = JobExecution.Status.CANCELLED
            job.finished_at = timezone.now()
            job.lease_expires_at = None
            fields.extend(["status", "finished_at", "lease_expires_at"])
        job.save(update_fields=fields)
        return job.status


def execute_job(
    job_id: uuid.UUID,
    *,
    generation: int,
    operation: Callable[[Callable[[int], bool]], dict[str, Any]],
) -> JobOutcome:
    now = timezone.now()
    with transaction.atomic():
        job = JobExecution.objects.select_for_update().get(id=job_id)
        if job.status == JobExecution.Status.SUCCEEDED:
            return JobOutcome("duplicate", dict(job.result), "hasil idempoten digunakan kembali")
        if job.status == JobExecution.Status.CANCELLED or job.cancel_requested:
            return JobOutcome("cancelled", {}, "task dibatalkan")
        if job.generation != generation:
            return JobOutcome("stale", {}, "generation task sudah berubah")
        if job.expires_at <= now:
            job.status = JobExecution.Status.CANCELLED
            job.finished_at = now
            job.save(update_fields=["status", "finished_at", "updated_at"])
            return JobOutcome("expired", {}, "task kedaluwarsa")
        if not _snapshots_valid(job):
            job.status = JobExecution.Status.CANCELLED
            job.cancel_requested = True
            job.finished_at = now
            job.save(update_fields=["status", "cancel_requested", "finished_at", "updated_at"])
            return JobOutcome("unauthorized", {}, "permission atau feature flag berubah")
        if (
            job.status == JobExecution.Status.RUNNING
            and job.lease_expires_at
            and job.lease_expires_at > now
        ):
            return JobOutcome("duplicate", {}, "delivery duplikat ditahan lease")
        policy = QUEUE_POLICIES[job.queue]
        active = JobExecution.objects.filter(
            queue=job.queue,
            status=JobExecution.Status.RUNNING,
            lease_expires_at__gt=now,
        ).exclude(id=job.id)
        if active.count() >= policy.max_active_jobs:
            return JobOutcome("saturated", {}, "batas active jobs tercapai")
        job.status = JobExecution.Status.RUNNING
        job.started_at = job.started_at or now
        job.lease_expires_at = now + timedelta(seconds=policy.hard_timeout + 30)
        job.attempts += 1
        job.save(
            update_fields=[
                "status",
                "started_at",
                "lease_expires_at",
                "attempts",
                "updated_at",
            ]
        )
    try:
        result = operation(
            lambda value: update_progress(job_id, generation=generation, progress=value)
        )
    except Exception as exc:
        with transaction.atomic():
            job = JobExecution.objects.select_for_update().get(id=job_id)
            if job.generation == generation:
                job.status = JobExecution.Status.FAILED
                job.last_error = _error_fingerprint(exc)
                job.finished_at = timezone.now()
                job.lease_expires_at = None
                job.save(
                    update_fields=[
                        "status",
                        "last_error",
                        "finished_at",
                        "lease_expires_at",
                        "updated_at",
                    ]
                )
        return JobOutcome("failed", {}, _error_fingerprint(exc))
    with transaction.atomic():
        job = JobExecution.objects.select_for_update().get(id=job_id)
        if job.generation != generation or job.cancel_requested or not _snapshots_valid(job):
            job.status = JobExecution.Status.CANCELLED
            job.result = {}
            job.result_hash = ""
            job.finished_at = timezone.now()
            job.lease_expires_at = None
            job.save(
                update_fields=[
                    "status",
                    "result",
                    "result_hash",
                    "finished_at",
                    "lease_expires_at",
                    "updated_at",
                ]
            )
            return JobOutcome("stale", {}, "hasil lama dibuang")
        job.status = JobExecution.Status.SUCCEEDED
        job.result = result
        job.result_hash = _digest(result)
        job.progress = 100
        job.finished_at = timezone.now()
        job.lease_expires_at = None
        job.last_error = ""
        job.save(
            update_fields=[
                "status",
                "result",
                "result_hash",
                "progress",
                "finished_at",
                "lease_expires_at",
                "last_error",
                "updated_at",
            ]
        )
        return JobOutcome("succeeded", dict(result))


def reconcile_stale_jobs() -> tuple[int, int]:
    now = timezone.now()
    cancelled = JobExecution.objects.filter(
        status__in=[JobExecution.Status.QUEUED, JobExecution.Status.RUNNING],
        expires_at__lte=now,
    ).update(
        status=JobExecution.Status.CANCELLED,
        cancel_requested=True,
        finished_at=now,
        lease_expires_at=None,
    )
    stale_ids = list(
        JobExecution.objects.filter(
            status=JobExecution.Status.RUNNING,
            lease_expires_at__lte=now,
            expires_at__gt=now,
            cancel_requested=False,
        ).values_list("id", flat=True)
    )
    requeued = 0
    for job_id in stale_ids:
        with transaction.atomic():
            job = JobExecution.objects.select_for_update().get(id=job_id)
            if job.status != JobExecution.Status.RUNNING or job.lease_expires_at > now:
                continue
            job.status = JobExecution.Status.QUEUED
            job.generation += 1
            job.lease_expires_at = None
            job.save(update_fields=["status", "generation", "lease_expires_at", "updated_at"])
            requeued += 1
    return requeued, cancelled
