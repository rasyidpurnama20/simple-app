from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from django.core import signing
from django.db.models import QuerySet
from django.utils import timezone

from obe.identity.services import require_permission
from obe.shared.models import AuditEvent, AuditSensitivePayload
from obe.shared.services import ActorContext, record_change


@dataclass(frozen=True)
class SignedAuditExport:
    content: bytes
    sha256: str
    signature: str


def verify_audit_chain(events: QuerySet[AuditEvent] | None = None) -> tuple[bool, str]:
    ordered = (AuditEvent.objects.all() if events is None else events).order_by("occurred_at", "id")
    previous = "0" * 64
    for event in ordered.iterator():
        if event.previous_hash != previous or event.integrity_hash != event.expected_hash():
            return False, str(event.id)
        previous = event.integrity_hash
    return True, previous


def search_audit(
    *,
    user,
    action: str = "",
    object_type: str = "",
    object_id: str = "",
    correlation_id: str = "",
):
    require_permission(user, "audit.view")
    events = AuditEvent.objects.all()
    if action:
        events = events.filter(action=action)
    if object_type:
        events = events.filter(object_type=object_type)
    if object_id:
        events = events.filter(object_id=object_id)
    if correlation_id:
        events = events.filter(correlation_id=correlation_id)
    return events


def export_audit(*, user, events: QuerySet[AuditEvent]) -> SignedAuditExport:
    require_permission(user, "audit.export")
    rows = [
        {
            "id": str(event.id),
            "occurred_at": event.occurred_at.isoformat(),
            "actor_id": event.actor_id,
            "actor_role": event.actor_role,
            "assignment_reference": event.assignment_reference,
            "action": event.action,
            "object_type": event.object_type,
            "object_id": event.object_id,
            "summary": event.summary,
            "reason": event.reason,
            "correlation_id": str(event.correlation_id),
            "outcome": event.outcome,
            "integrity_hash": event.integrity_hash,
        }
        for event in events.order_by("occurred_at", "id")
    ]
    content = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(content).hexdigest()
    signature = signing.Signer(salt="obe.audit.export.v1").sign(digest)
    record_change(
        actor=ActorContext(str(user.pk), user.get_username()),
        action="export.audit",
        object_type="audit-export",
        object_id=digest[:16],
        summary=f"Signed audit export with {len(rows)} rows",
        reason="authorized audit export",
        after={"sha256": digest, "row_count": len(rows)},
    )
    return SignedAuditExport(content=content, sha256=digest, signature=signature)


def verify_signed_export(export: SignedAuditExport) -> bool:
    digest = hashlib.sha256(export.content).hexdigest()
    try:
        unsigned = signing.Signer(salt="obe.audit.export.v1").unsign(export.signature)
    except signing.BadSignature:
        return False
    return digest == export.sha256 == unsigned


def purge_expired_sensitive_payloads(*, actor_id: str = "system") -> int:
    expired = AuditSensitivePayload.objects.filter(retention_until__lt=timezone.localdate())
    count = expired.count()
    if count:
        expired.delete()
        record_change(
            actor=ActorContext(actor_id, "retention-job"),
            action="audit.sensitive.retention",
            object_type="audit-sensitive-payload",
            object_id=timezone.localdate().isoformat(),
            summary=f"Expired sensitive audit payloads purged: {count}",
            after={"purged": count},
            reason="configured retention elapsed",
        )
    return count
