import hashlib
import json
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any, TypeVar, cast

from django.core.exceptions import ValidationError
from django.db import OperationalError, models, transaction

from obe.shared.models import AuditEvent, OutboxEvent

ModelT = TypeVar("ModelT", bound=models.Model)


@dataclass(frozen=True)
class ActorContext:
    actor_id: str
    label: str = ""
    scope: str = ""
    correlation_id: uuid.UUID = field(default_factory=uuid.uuid4)


def _digest(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


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
    event_type: str | None = None,
) -> AuditEvent:
    before, after = before or {}, after or {}
    with transaction.atomic():
        audit = AuditEvent.objects.create(
            actor_id=actor.actor_id,
            actor_label=actor.label,
            actor_scope=actor.scope,
            action=action,
            object_type=object_type,
            object_id=object_id,
            summary=summary,
            before=before,
            after=after,
            reason=reason,
            correlation_id=actor.correlation_id,
            integrity_hash=_digest(
                {"actor": asdict(actor), "action": action, "object": object_id, "after": after}
            ),
        )
        if event_type:
            OutboxEvent.objects.create(
                event_type=event_type,
                aggregate_id=object_id,
                actor_id=actor.actor_id,
                correlation_id=actor.correlation_id,
                payload={"audit_id": str(audit.id), "after": after},
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
