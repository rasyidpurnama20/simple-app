from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from obe.quality.models import IntegrityIssue, IntegrityValidationRun
from obe.shared.services import ActorContext, record_change

VALIDATOR_VERSION = "pr18-v1"
CODE_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9._-]{1,79}$")


@dataclass(frozen=True)
class IssueSpec:
    severity: str
    reason_code: str
    object_type: str
    object_id: str
    impact: str
    evidence: tuple[dict[str, Any], ...]
    source_snapshot: dict[str, Any]
    fingerprint: str


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _checksum(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _issue(
    *,
    severity: str,
    reason_code: str,
    object_type: str,
    object_id: str,
    impact: str,
    record: dict[str, Any],
    field: str = "",
    detail: str = "",
) -> IssueSpec:
    fingerprint = _checksum(
        {
            "reason": reason_code,
            "object_type": object_type,
            "object_id": object_id,
            "field": field,
        }
    )
    return IssueSpec(
        severity,
        reason_code,
        object_type,
        object_id,
        impact,
        ({"field": field, "detail": detail},),
        record,
        fingerprint,
    )


def _parse_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def validate_record(
    record: dict[str, Any],
    *,
    object_type: str,
    required_fields: Iterable[str] = ("code",),
) -> tuple[IssueSpec, ...]:
    object_id = str(record.get("id") or record.get("code") or "unknown")
    issues: list[IssueSpec] = []
    for field in required_fields:
        value = record.get(field)
        if value is None or value == "" or value == []:
            issues.append(
                _issue(
                    severity=str(IntegrityIssue.Severity.BLOCKING),
                    reason_code="REQUIRED_FIELD_MISSING",
                    object_type=object_type,
                    object_id=object_id,
                    impact="Record tidak dapat digunakan pada keputusan resmi.",
                    record=record,
                    field=field,
                    detail="field wajib kosong",
                )
            )
    code = record.get("code")
    if code and not CODE_PATTERN.fullmatch(str(code)):
        issues.append(
            _issue(
                severity=str(IntegrityIssue.Severity.BLOCKING),
                reason_code="CODE_INVALID",
                object_type=object_type,
                object_id=object_id,
                impact="Kode tidak memenuhi kontrak identifier.",
                record=record,
                field="code",
                detail=str(code),
            )
        )
    for field in ("credits", "sks"):
        if field in record:
            try:
                value = Decimal(str(record[field]))
                valid = Decimal("0") < value <= Decimal("24")
            except (InvalidOperation, TypeError):
                valid = False
            if not valid:
                issues.append(
                    _issue(
                        severity=str(IntegrityIssue.Severity.BLOCKING),
                        reason_code="CREDITS_OUT_OF_RANGE",
                        object_type=object_type,
                        object_id=object_id,
                        impact="SKS tidak dapat dipakai pada perhitungan akademik.",
                        record=record,
                        field=field,
                        detail=str(record[field]),
                    )
                )
    try:
        semester_valid = 1 <= int(record.get("semester") or 0) <= 14
    except (TypeError, ValueError):
        semester_valid = False
    if "semester" in record and not semester_valid:
        issues.append(
            _issue(
                severity=str(IntegrityIssue.Severity.BLOCKING),
                reason_code="SEMESTER_OUT_OF_RANGE",
                object_type=object_type,
                object_id=object_id,
                impact="Semester tidak logis.",
                record=record,
                field="semester",
                detail=str(record.get("semester")),
            )
        )
    for field in ("score", "value", "weight"):
        if field in record and record[field] is not None:
            try:
                value = Decimal(str(record[field]))
                valid = Decimal("0") <= value <= Decimal("100")
            except (InvalidOperation, TypeError):
                valid = False
            if not valid:
                issues.append(
                    _issue(
                        severity=str(IntegrityIssue.Severity.BLOCKING),
                        reason_code="VALUE_OUT_OF_RANGE",
                        object_type=object_type,
                        object_id=object_id,
                        impact="Nilai atau bobot berada di luar rentang 0–100.",
                        record=record,
                        field=field,
                        detail=str(record[field]),
                    )
                )
    weights = record.get("weights")
    if isinstance(weights, list):
        total = sum((Decimal(str(item.get("weight", 0))) for item in weights), Decimal("0"))
        if total != Decimal("100"):
            issues.append(
                _issue(
                    severity=str(IntegrityIssue.Severity.BLOCKING),
                    reason_code="WEIGHTS_NOT_100",
                    object_type=object_type,
                    object_id=object_id,
                    impact="Pemetaan berbobot tidak boleh diaktifkan.",
                    record=record,
                    field="weights",
                    detail=f"total={total}",
                )
            )
    effective_from = _parse_date(record.get("effective_from"))
    effective_to = _parse_date(record.get("effective_to"))
    if record.get("effective_from") and effective_from is None:
        issues.append(
            _issue(
                severity=str(IntegrityIssue.Severity.BLOCKING),
                reason_code="DATE_INVALID",
                object_type=object_type,
                object_id=object_id,
                impact="Tanggal efektif tidak dapat ditafsirkan.",
                record=record,
                field="effective_from",
            )
        )
    if effective_to and (effective_from is None or effective_to < effective_from):
        issues.append(
            _issue(
                severity=str(IntegrityIssue.Severity.BLOCKING),
                reason_code="DATE_RANGE_INVALID",
                object_type=object_type,
                object_id=object_id,
                impact="Periode efektif tidak logis.",
                record=record,
                field="effective_to",
            )
        )
    checksum = record.get("checksum")
    if checksum and (len(str(checksum)) != 64 or not re.fullmatch(r"[0-9a-f]{64}", str(checksum))):
        issues.append(
            _issue(
                severity=str(IntegrityIssue.Severity.BLOCKING),
                reason_code="CHECKSUM_INVALID",
                object_type=object_type,
                object_id=object_id,
                impact="Integritas payload tidak dapat diverifikasi.",
                record=record,
                field="checksum",
            )
        )
    if record.get("evidence_required") and not record.get("evidence"):
        issues.append(
            _issue(
                severity=str(IntegrityIssue.Severity.WARNING),
                reason_code="EVIDENCE_MISSING",
                object_type=object_type,
                object_id=object_id,
                impact="Reviewer harus melengkapi bukti sebelum approval.",
                record=record,
                field="evidence",
            )
        )
    return tuple(issues)


def validate_collection(
    records: Iterable[dict[str, Any]],
    *,
    object_type: str,
    required_fields: Iterable[str] = ("code",),
) -> tuple[IssueSpec, ...]:
    records = tuple(records)
    issues = [
        issue
        for record in records
        for issue in validate_record(
            record,
            object_type=object_type,
            required_fields=required_fields,
        )
    ]
    by_code: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        by_code.setdefault(str(record.get("code", "")), []).append(record)
    for code, matches in by_code.items():
        if code and len(matches) > 1:
            issues.append(
                _issue(
                    severity=str(IntegrityIssue.Severity.BLOCKING),
                    reason_code="DUPLICATE_CODE",
                    object_type=object_type,
                    object_id=code,
                    impact="Record duplikat menyebabkan keputusan ambigu.",
                    record={"matches": matches},
                    field="code",
                    detail=f"count={len(matches)}",
                )
            )
    parent_ids = {str(record.get("id")) for record in records if record.get("id")}
    for record in records:
        parent = record.get("parent_id")
        if parent and str(parent) not in parent_ids:
            issues.append(
                _issue(
                    severity=str(IntegrityIssue.Severity.BLOCKING),
                    reason_code="ORPHAN_REFERENCE",
                    object_type=object_type,
                    object_id=str(record.get("id") or record.get("code") or "unknown"),
                    impact="Relasi tidak memiliki record induk.",
                    record=record,
                    field="parent_id",
                    detail=str(parent),
                )
            )
    return tuple(issues)


@transaction.atomic
def persist_validation(
    *,
    dataset_name: str,
    source: Any,
    issues: Iterable[IssueSpec],
    owner,
    actor: ActorContext,
) -> IntegrityValidationRun:
    checksum = _checksum(source)
    specs = tuple(issues)
    run, _ = IntegrityValidationRun.objects.get_or_create(
        source_checksum=checksum,
        validator_version=VALIDATOR_VERSION,
        defaults={"dataset_name": dataset_name},
    )
    counts = {severity: 0 for severity in IntegrityIssue.Severity.values}
    for spec in specs:
        counts[spec.severity] += 1
        issue, created = IntegrityIssue.objects.get_or_create(
            fingerprint=spec.fingerprint,
            defaults={
                "severity": spec.severity,
                "reason_code": spec.reason_code,
                "object_type": spec.object_type,
                "object_id": spec.object_id,
                "impact": spec.impact,
                "owner": owner,
                "evidence": list(spec.evidence),
                "source_snapshot": spec.source_snapshot,
                "source_checksum": checksum,
            },
        )
        if not created and issue.status in {
            IntegrityIssue.Status.RESOLVED,
            IntegrityIssue.Status.VERIFIED,
        }:
            issue.status = IntegrityIssue.Status.REOPENED
            issue.lock_version += 1
            issue.save(update_fields=["status", "lock_version", "updated_at"])
    run.status = (
        IntegrityValidationRun.Status.BLOCKED
        if counts[IntegrityIssue.Severity.BLOCKING]
        else IntegrityValidationRun.Status.PASSED
    )
    run.statistics = {**counts, "total": len(specs)}
    run.finished_at = timezone.now()
    run.save(update_fields=["status", "statistics", "finished_at"])
    record_change(
        actor=actor,
        action="quality.integrity-validated",
        object_type="integrity-validation-run",
        object_id=str(run.id),
        summary=f"Validasi {dataset_name}: {run.status}",
        after=run.statistics,
        reason="Validasi deterministik sebelum data digunakan pada keluaran resmi",
    )
    return run


TRANSITIONS = {
    IntegrityIssue.Status.OPEN: {
        IntegrityIssue.Status.ASSIGNED,
        IntegrityIssue.Status.INVESTIGATING,
        IntegrityIssue.Status.ACCEPTED_RISK,
    },
    IntegrityIssue.Status.ASSIGNED: {IntegrityIssue.Status.INVESTIGATING},
    IntegrityIssue.Status.INVESTIGATING: {
        IntegrityIssue.Status.RESOLVED,
        IntegrityIssue.Status.ACCEPTED_RISK,
    },
    IntegrityIssue.Status.RESOLVED: {
        IntegrityIssue.Status.VERIFIED,
        IntegrityIssue.Status.REOPENED,
    },
    IntegrityIssue.Status.ACCEPTED_RISK: {IntegrityIssue.Status.REOPENED},
    IntegrityIssue.Status.REOPENED: {IntegrityIssue.Status.INVESTIGATING},
}


@transaction.atomic
def transition_issue(
    issue: IntegrityIssue,
    *,
    target: str,
    actor_user,
    actor: ActorContext,
    authorized: bool,
    expected_lock_version: int,
    reason: str,
) -> IntegrityIssue:
    if not authorized:
        raise PermissionDenied("Actor tidak berwenang mengubah integrity issue")
    locked = IntegrityIssue.objects.select_for_update().get(pk=issue.pk)
    if locked.lock_version != expected_lock_version:
        raise ValidationError("Integrity issue stale; muat ulang sebelum melanjutkan")
    if target not in TRANSITIONS.get(locked.status, set()):
        raise ValidationError(f"Transisi issue {locked.status} → {target} tidak valid")
    if target == IntegrityIssue.Status.ACCEPTED_RISK and not reason.strip():
        raise ValidationError("Accepted risk memerlukan alasan")
    locked.status = target
    locked.lock_version += 1
    if target == IntegrityIssue.Status.ACCEPTED_RISK:
        locked.accepted_risk_reason = reason
    if target == IntegrityIssue.Status.RESOLVED:
        locked.resolution = reason
        locked.resolved_at = timezone.now()
    if target == IntegrityIssue.Status.VERIFIED:
        locked.verified_by = actor_user
        locked.verified_at = timezone.now()
    locked.full_clean()
    locked.save()
    record_change(
        actor=actor,
        action="quality.integrity-status",
        object_type="integrity-issue",
        object_id=str(locked.public_id),
        summary=f"Integrity issue menjadi {target}",
        after={"status": target, "reason_code": locked.reason_code},
        reason=reason,
    )
    return locked


def assert_data_usable(*, object_type: str, object_id: str, purpose: str) -> None:
    blocked = IntegrityIssue.objects.filter(
        object_type=object_type,
        object_id=object_id,
        severity=IntegrityIssue.Severity.BLOCKING,
    ).exclude(status=IntegrityIssue.Status.VERIFIED)
    if blocked.exists():
        codes = ", ".join(blocked.order_by("reason_code").values_list("reason_code", flat=True))
        raise ValidationError(f"Data diblokir untuk {purpose}: {codes}")
