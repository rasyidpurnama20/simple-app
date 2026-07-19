import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, TypeVar, cast

from django.core.exceptions import ValidationError
from django.db import OperationalError, connection, models, transaction
from django.utils import timezone

from obe.shared.events import DEFAULT_CONSUMERS, create_outbox_event
from obe.shared.models import AuditEvent, AuditReference, AuditSensitivePayload

ModelT = TypeVar("ModelT", bound=models.Model)


@dataclass(frozen=True)
class ActorContext:
    actor_id: str
    label: str = ""
    scope: str = ""
    correlation_id: uuid.UUID = field(default_factory=uuid.uuid4)


SENSITIVE_AUDIT_KEY = re.compile(
    r"(password|secret|token|answer|prompt|student_number|nim|raw_grade|file_path)", re.I
)
REASON_REQUIRED_PREFIXES = (
    "approval.",
    "assessment.grade",
    "export.",
    "feature-flag.",
    "import.",
    "integration.write",
    "override.",
    "rule.",
)


def _audit_summary(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): "[redacted]" if SENSITIVE_AUDIT_KEY.search(str(key)) else _audit_summary(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_audit_summary(item) for item in value[:100]]
    if isinstance(value, str):
        return value[:500]
    return value


def record_change(
    *,
    actor: ActorContext,
    action: str,
    object_type: str,
    object_id: str,
    summary: str,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    reason: str = "",
    actor_role: str = "",
    assignment_reference: str = "",
    ip_address: str | None = None,
    user_agent: str = "",
    outcome: str = "success",
    sensitive_payload: dict[str, Any] | None = None,
    retention_days: int = 2_555,
    references: tuple[tuple[str, str, str], ...] = (),
    event_type: str | None = None,
    aggregate_version: int = 1,
    event_consumers: tuple[str, ...] = DEFAULT_CONSUMERS,
) -> AuditEvent:
    if any(action.startswith(prefix) for prefix in REASON_REQUIRED_PREFIXES) and not reason.strip():
        raise ValidationError("Aksi kritis wajib memiliki alasan audit")
    before, after = _audit_summary(before or {}), _audit_summary(after or {})
    with transaction.atomic():
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", ["obe-audit-chain"])
        audit = AuditEvent.objects.create(
            actor_id=actor.actor_id,
            actor_label=actor.label,
            actor_scope=actor.scope,
            actor_role=actor_role,
            assignment_reference=assignment_reference,
            action=action,
            object_type=object_type,
            object_id=object_id,
            summary=summary,
            before=before,
            after=after,
            reason=reason,
            correlation_id=actor.correlation_id,
            ip_address=ip_address,
            user_agent=user_agent[:255],
            outcome=outcome,
            retention_until=(timezone.now() + timedelta(days=retention_days)).date(),
        )
        if sensitive_payload:
            AuditSensitivePayload.objects.create(
                audit=audit,
                payload=sensitive_payload,
                retention_until=(timezone.now() + timedelta(days=retention_days)).date(),
            )
        AuditReference.objects.bulk_create(
            [
                AuditReference(
                    source_type=source_type,
                    source_id=source_id,
                    audit=audit,
                    label=label,
                )
                for source_type, source_id, label in references
            ]
        )
        if event_type:
            create_outbox_event(
                event_type=event_type,
                aggregate_id=object_id,
                aggregate_version=aggregate_version,
                actor_id=actor.actor_id,
                correlation_id=actor.correlation_id,
                payload={"audit_id": str(audit.id), "after": after},
                consumers=event_consumers,
            )
    return audit


def update_versioned(
    instance: ModelT,
    *,
    expected_lock_version: int,
    actor_id: str,
    changes: dict[str, Any],
) -> ModelT:
    protected = {"id", "pk", "public_id", "version", "lock_version", "created_at"}
    if protected.intersection(changes):
        raise ValidationError("Field identitas/versioning tidak boleh diubah langsung")
    with transaction.atomic():
        locked = type(instance).objects.select_for_update().get(pk=instance.pk)
        if locked.lock_version != expected_lock_version:
            raise ValidationError("Optimistic lock conflict; muat ulang data terbaru")
        field_names = {field.name for field in locked._meta.concrete_fields}
        unknown = set(changes) - field_names
        if unknown:
            raise ValidationError(f"Field perubahan tidak dikenal: {', '.join(sorted(unknown))}")
        for field_name, value in changes.items():
            setattr(locked, field_name, value)
        locked.lock_version += 1
        locked.updated_by_actor_id = actor_id
        locked.full_clean()
        locked.save(update_fields=[*changes, "lock_version", "updated_by_actor_id", "updated_at"])
    return cast(ModelT, locked)


def create_versioned(model: type[ModelT], *, actor_id: str, **fields: Any) -> ModelT:
    instance = model(
        **fields,
        created_by_actor_id=actor_id,
        updated_by_actor_id=actor_id,
    )
    instance.full_clean()
    instance.save()
    return instance


def run_with_deadlock_retry(operation: Callable[[], ModelT], *, attempts: int = 3) -> ModelT:
    if attempts < 1:
        raise ValueError("attempts minimal 1")
    for attempt in range(attempts):
        try:
            with transaction.atomic():
                return operation()
        except OperationalError as exc:
            sqlstate = getattr(exc, "pgcode", None) or getattr(exc.__cause__, "sqlstate", None)
            if sqlstate not in {"40P01", "40001"} or attempt == attempts - 1:
                raise
    raise RuntimeError("Deadlock retry tidak mencapai terminal state")
