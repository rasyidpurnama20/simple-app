import hashlib
import json
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

from django.db import transaction

from obe.shared.models import AuditEvent, OutboxEvent


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
