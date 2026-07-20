from __future__ import annotations

import csv
import hashlib
import html
import io
import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from obe.assessment.selectors import attainment_portfolio_rows
from obe.identity.services import can, require_permission
from obe.quality.models import (
    AcademicFeedback,
    ImprovementAction,
    PortfolioSnapshot,
    QualityCycle,
    QualityFinding,
    QualityReport,
    QualityStandard,
)
from obe.shared.services import ActorContext, record_change

PORTFOLIO_TRANSITIONS = {
    PortfolioSnapshot.Status.DRAFT: {PortfolioSnapshot.Status.GPM_REVIEW},
    PortfolioSnapshot.Status.GPM_REVIEW: {
        PortfolioSnapshot.Status.RETURNED,
        PortfolioSnapshot.Status.APPROVED,
    },
    PortfolioSnapshot.Status.RETURNED: {PortfolioSnapshot.Status.DRAFT},
    PortfolioSnapshot.Status.APPROVED: {PortfolioSnapshot.Status.PUBLISHED},
    PortfolioSnapshot.Status.PUBLISHED: {
        PortfolioSnapshot.Status.SUPERSEDED,
        PortfolioSnapshot.Status.ARCHIVED,
    },
}

ACTION_TRANSITIONS = {
    ImprovementAction.Status.PLANNED: {
        ImprovementAction.Status.ACTIVE,
        ImprovementAction.Status.BLOCKED,
        ImprovementAction.Status.ACCEPTED_RISK,
    },
    ImprovementAction.Status.ACTIVE: {
        ImprovementAction.Status.BLOCKED,
        ImprovementAction.Status.COMPLETED,
    },
    ImprovementAction.Status.BLOCKED: {
        ImprovementAction.Status.ACTIVE,
        ImprovementAction.Status.REOPENED,
    },
    ImprovementAction.Status.COMPLETED: {
        ImprovementAction.Status.EFFECTIVE,
        ImprovementAction.Status.INEFFECTIVE,
    },
    ImprovementAction.Status.INEFFECTIVE: {ImprovementAction.Status.REOPENED},
    ImprovementAction.Status.REOPENED: {ImprovementAction.Status.ACTIVE},
}

REPORT_TRANSITIONS = {
    QualityReport.Status.DRAFT: {QualityReport.Status.GPM_REVIEWED},
    QualityReport.Status.GPM_REVIEWED: {QualityReport.Status.PRODI_APPROVED},
    QualityReport.Status.PRODI_APPROVED: {QualityReport.Status.TPMF_REVIEWED},
    QualityReport.Status.TPMF_REVIEWED: {QualityReport.Status.PUBLISHED},
    QualityReport.Status.PUBLISHED: {QualityReport.Status.CORRECTION},
}

FEEDBACK_TRANSITIONS = {
    AcademicFeedback.Status.NEW: {
        AcademicFeedback.Status.VERIFIED,
        AcademicFeedback.Status.CLARIFICATION,
        AcademicFeedback.Status.REJECTED,
    },
    AcademicFeedback.Status.CLARIFICATION: {
        AcademicFeedback.Status.VERIFIED,
        AcademicFeedback.Status.REJECTED,
    },
    AcademicFeedback.Status.VERIFIED: {AcademicFeedback.Status.ACTION_PLANNED},
    AcademicFeedback.Status.ACTION_PLANNED: {AcademicFeedback.Status.ACTIONED},
    AcademicFeedback.Status.ACTIONED: {AcademicFeedback.Status.CLOSED},
    AcademicFeedback.Status.REJECTED: {AcademicFeedback.Status.REOPENED},
    AcademicFeedback.Status.CLOSED: {AcademicFeedback.Status.REOPENED},
    AcademicFeedback.Status.REOPENED: {
        AcademicFeedback.Status.VERIFIED,
        AcademicFeedback.Status.CLARIFICATION,
    },
}

REQUIRED_REPORT_SECTIONS = {
    "rps",
    "assessment",
    "attendance",
    "scores",
    "attainment",
    "evidence",
    "complaints",
    "findings",
    "cqi",
    "effectiveness",
}


@dataclass(frozen=True)
class ExportArtifact:
    content: bytes
    mime_type: str
    checksum: str
    filename: str


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()


def _checksum(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _actor(user, scope: str = "quality") -> ActorContext:
    return ActorContext(str(user.pk), user.get_username(), scope)


def _portfolio_package(
    *,
    portfolio_type: str,
    scope_id: str,
    period: str,
    version: int,
    sections: dict[str, Any],
    source_versions: dict[str, Any],
    evidence_manifest_ids: list[str],
    incomplete_sections: list[str],
) -> dict[str, Any]:
    return {
        "contract": "obe-portfolio/1",
        "portfolio_type": portfolio_type,
        "scope_id": scope_id,
        "period": period,
        "version": version,
        "sections": sections,
        "source_versions": source_versions,
        "evidence_manifest_ids": sorted(evidence_manifest_ids),
        "incomplete_sections": sorted(incomplete_sections),
    }


@transaction.atomic
def generate_portfolio(
    *,
    portfolio_type: str,
    scope_id: str,
    period: str,
    evidence: list[dict[str, Any]],
    findings: list[dict[str, Any]],
    actions: list[dict[str, Any]],
    source_versions: dict[str, Any],
    user,
    supersedes: PortfolioSnapshot | None = None,
    rps: list[dict[str, Any]] | None = None,
    assessments: list[dict[str, Any]] | None = None,
    scores: list[dict[str, Any]] | None = None,
) -> PortfolioSnapshot:
    require_permission(
        user,
        "portfolio.generate",
        scope_type=portfolio_type,
        scope_id=scope_id,
        owner_id=scope_id if portfolio_type == PortfolioSnapshot.PortfolioType.STUDENT else "",
    )
    if portfolio_type not in PortfolioSnapshot.PortfolioType.values:
        raise ValidationError("Jenis portfolio tidak didukung")
    rps = rps or []
    assessments = assessments or []
    scores = scores or []
    if portfolio_type == PortfolioSnapshot.PortfolioType.STUDENT and any(
        str(row.get("owner_id", "")) != scope_id for row in evidence
    ):
        raise ValidationError("Portfolio mahasiswa hanya boleh memakai bukti miliknya")
    attainment = attainment_portfolio_rows(scope_type=portfolio_type, scope_id=scope_id)
    verified_evidence = [row for row in evidence if row.get("status") == "verified"]
    evidence_ids = [str(row["manifest_id"]) for row in verified_evidence]
    incomplete = []
    if not attainment:
        incomplete.append("attainment")
    elif any(row["status"] != "valid" or row["blocking_reasons"] for row in attainment):
        incomplete.append("attainment-blocked")
    if not verified_evidence or len(verified_evidence) != len(evidence):
        incomplete.append("evidence")
    if not rps or any(row.get("status") not in {"active", "approved"} for row in rps):
        incomplete.append("rps")
    if not assessments or any(
        row.get("status") not in {"active", "approved", "verified"} for row in assessments
    ):
        incomplete.append("assessments")
    if not scores or any(row.get("status") not in {"published", "regraded"} for row in scores):
        incomplete.append("scores")
    if any(row.get("status") not in {"closed", "accepted-risk"} for row in findings):
        incomplete.append("findings")
    if any(row.get("status") not in {"effective", "accepted-risk"} for row in actions):
        incomplete.append("actions")
    sections = {
        "rps": rps,
        "assessments": assessments,
        "scores": scores,
        "attainment": attainment,
        "evidence": verified_evidence,
        "findings": findings,
        "cqi_actions": actions,
    }
    version = (
        PortfolioSnapshot.objects.filter(
            portfolio_type=portfolio_type, scope_id=scope_id, period=period
        )
        .order_by("-version")
        .values_list("version", flat=True)
        .first()
        or 0
    ) + 1
    package = _portfolio_package(
        portfolio_type=portfolio_type,
        scope_id=scope_id,
        period=period,
        version=version,
        sections=sections,
        source_versions=source_versions,
        evidence_manifest_ids=evidence_ids,
        incomplete_sections=incomplete,
    )
    portfolio = PortfolioSnapshot(
        portfolio_type=portfolio_type,
        scope_id=scope_id,
        period=period,
        version=version,
        sections=sections,
        source_versions=source_versions,
        evidence_manifest_ids=evidence_ids,
        incomplete_sections=sorted(set(incomplete)),
        package_checksum=_checksum(package),
        generated_by=user,
        supersedes=supersedes,
        created_by_actor_id=str(user.pk),
        updated_by_actor_id=str(user.pk),
    )
    portfolio.full_clean()
    portfolio.save()
    if supersedes and supersedes.status == PortfolioSnapshot.Status.PUBLISHED:
        PortfolioSnapshot.objects.filter(pk=supersedes.pk).update(
            status=PortfolioSnapshot.Status.SUPERSEDED,
            updated_by_actor_id=str(user.pk),
        )
    return portfolio


@transaction.atomic
def transition_portfolio(
    portfolio: PortfolioSnapshot, *, target: str, user, note: str = ""
) -> PortfolioSnapshot:
    locked = PortfolioSnapshot.objects.select_for_update().get(pk=portfolio.pk)
    if target not in PORTFOLIO_TRANSITIONS.get(locked.status, set()):
        raise ValidationError(f"Transisi portfolio {locked.status} -> {target} tidak valid")
    action_map: dict[str, str] = {
        str(PortfolioSnapshot.Status.GPM_REVIEW): "portfolio.review",
        str(PortfolioSnapshot.Status.RETURNED): "portfolio.review",
        str(PortfolioSnapshot.Status.APPROVED): "portfolio.approve",
        str(PortfolioSnapshot.Status.PUBLISHED): "portfolio.publish",
    }
    action = action_map.get(target, "portfolio.generate")
    require_permission(user, action, scope_type=locked.portfolio_type, scope_id=locked.scope_id)
    if target == PortfolioSnapshot.Status.GPM_REVIEW:
        locked.reviewed_by = user
    elif target == PortfolioSnapshot.Status.APPROVED:
        if not locked.reviewed_by_id or user.pk in {locked.generated_by_id, locked.reviewed_by_id}:
            raise ValidationError("Approval portfolio memerlukan maker-checker terpisah")
        if locked.incomplete_sections:
            raise ValidationError("Portfolio belum lengkap")
        locked.approved_by = user
    elif target == PortfolioSnapshot.Status.PUBLISHED:
        if not locked.approved_by_id:
            raise ValidationError("Portfolio belum approved")
        locked.published_at = timezone.now()
    elif target == PortfolioSnapshot.Status.RETURNED and not note.strip():
        raise ValidationError("Return for revision memerlukan catatan")
    locked.approval_history = [
        *locked.approval_history,
        {
            "from": locked.status,
            "to": target,
            "actor": str(user.pk),
            "at": timezone.now().isoformat(),
            "note": note,
        },
    ]
    before = locked.status
    locked.status = target
    locked.updated_by_actor_id = str(user.pk)
    locked.full_clean()
    locked.save()
    record_change(
        actor=_actor(user, "portfolio"),
        action=f"portfolio.{target}",
        object_type="portfolio",
        object_id=str(locked.public_id),
        summary="Lifecycle portfolio diperbarui",
        before={"status": before},
        after={"status": target},
        reason=note,
    )
    return locked


def _portfolio_export_payload(portfolio: PortfolioSnapshot) -> dict[str, Any]:
    payload = _portfolio_package(
        portfolio_type=portfolio.portfolio_type,
        scope_id=portfolio.scope_id,
        period=portfolio.period,
        version=portfolio.version,
        sections=portfolio.sections,
        source_versions=portfolio.source_versions,
        evidence_manifest_ids=portfolio.evidence_manifest_ids,
        incomplete_sections=portfolio.incomplete_sections,
    )
    if _checksum(payload) != portfolio.package_checksum:
        raise ValidationError("Checksum portfolio tidak cocok; regenerasi diperlukan")
    return payload


def _minimal_pdf(text: str) -> bytes:
    safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")[:5000]
    stream = f"BT /F1 9 Tf 40 780 Td ({safe}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(
        f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return bytes(output)


def export_portfolio(portfolio: PortfolioSnapshot, *, export_format: str) -> ExportArtifact:
    if portfolio.status not in {
        PortfolioSnapshot.Status.APPROVED,
        PortfolioSnapshot.Status.PUBLISHED,
    }:
        raise ValidationError("Export resmi hanya untuk portfolio approved/published")
    payload = _portfolio_export_payload(portfolio)
    basename = f"portfolio-{portfolio.portfolio_type}-{portfolio.scope_id}-v{portfolio.version}"
    if export_format == "html":
        content = (
            "<!doctype html><meta charset='utf-8'><title>OBE Portfolio</title><pre>"
            + html.escape(json.dumps(payload, ensure_ascii=False, indent=2))
            + "</pre>"
        ).encode()
        mime = "text/html; charset=utf-8"
    elif export_format == "csv":
        stream = io.StringIO(newline="")
        writer = csv.writer(stream)
        writer.writerow(["outcome", "actual", "target", "denominator", "coverage", "formula"])
        for row in payload["sections"]["attainment"]:
            writer.writerow(
                [
                    row["outcome_code"],
                    row["actual"],
                    row["target"],
                    row["denominator"],
                    row["coverage"],
                    row["formula_version"],
                ]
            )
        content = stream.getvalue().encode()
        mime = "text/csv; charset=utf-8"
    elif export_format == "pdf":
        content = _minimal_pdf(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        mime = "application/pdf"
    else:
        raise ValidationError("Format export harus html, csv, atau pdf")
    return ExportArtifact(
        content, mime, hashlib.sha256(content).hexdigest(), f"{basename}.{export_format}"
    )


@transaction.atomic
def evaluate_provus(
    *, period: str, attainment_rows: list[dict[str, Any]], user
) -> list[QualityFinding]:
    require_permission(user, "quality.validate")
    standards: dict[str, QualityStandard] = {}
    for standard in QualityStandard.objects.order_by("metric", "-version"):
        standards.setdefault(standard.metric, standard)
    findings = []
    for row in attainment_rows:
        metric = str(row["metric"])
        standard = standards.get(metric)
        if standard is None:
            raise ValidationError(f"Standard Provus tidak ditemukan: {metric}")
        actual = Decimal(str(row["actual"]))
        target = standard.target
        gap = actual - target
        classification = "below" if gap < 0 else "met" if gap == 0 else "exceeded"
        coverage = Decimal(str(row.get("coverage", 0)))
        confidence = "high" if coverage >= 90 else "medium" if coverage >= 70 else "low"
        source_id = (f"PROVUS-{period}-{row['scope_type']}-{row['scope_id']}-{metric}")[:160]
        finding, _ = QualityFinding.objects.update_or_create(
            source_id=source_id,
            defaults={
                "standard": standard,
                "scope": {
                    "period": period,
                    "scope_type": row["scope_type"],
                    "scope_id": row["scope_id"],
                    "metric": metric,
                },
                "actual": actual,
                "target": target,
                "gap": gap,
                "classification": classification,
                "denominator": int(row.get("denominator", 0)),
                "coverage": coverage,
                "confidence": confidence,
                "status": "open" if classification == "below" else "closed",
                "reason_codes": row.get("reason_codes", []),
                "source_snapshot": row,
            },
        )
        findings.append(finding)
    return findings


@transaction.atomic
def plan_improvement_action(
    *,
    finding: QualityFinding,
    root_cause: str,
    action: str,
    owner,
    due_at: datetime,
    success_indicator: str,
    user,
) -> ImprovementAction:
    require_permission(user, "quality.edit")
    if finding.classification != "below":
        raise ValidationError("CQI action hanya dibuat untuk gap di bawah target")
    if not all(value.strip() for value in (root_cause, action, success_indicator)):
        raise ValidationError("CQI action memerlukan sebab, tindakan, dan indikator")
    if due_at <= timezone.now():
        raise ValidationError("Deadline tindakan harus di masa depan")
    row = ImprovementAction(
        finding=finding,
        root_cause=root_cause,
        action=action,
        owner=owner,
        due_at=due_at,
        success_indicator=success_indicator,
        baseline={
            "actual": str(finding.actual),
            "target": str(finding.target),
            "gap": str(finding.gap),
            "coverage": str(finding.coverage),
        },
        created_by_actor_id=str(user.pk),
        updated_by_actor_id=str(user.pk),
    )
    row.full_clean()
    row.save()
    return row


@transaction.atomic
def transition_improvement_action(
    action: ImprovementAction,
    *,
    target: str,
    user,
    evidence: list[dict[str, Any]] | None = None,
    result: dict[str, Any] | None = None,
    reason: str = "",
) -> ImprovementAction:
    locked = ImprovementAction.objects.select_for_update().get(pk=action.pk)
    if target not in ACTION_TRANSITIONS.get(locked.status, set()):
        raise ValidationError(f"Transisi CQI {locked.status} -> {target} tidak valid")
    require_permission(user, "quality.resolve")
    if target == ImprovementAction.Status.ACTIVE:
        if user.pk == locked.owner_id:
            raise ValidationError("Owner tindakan tidak boleh menjadi approver sendiri")
        locked.approved_by = user
        locked.approval = {"actor": str(user.pk), "at": timezone.now().isoformat()}
    if target == ImprovementAction.Status.COMPLETED:
        if not evidence or not result:
            raise ValidationError("Penyelesaian CQI memerlukan hasil dan bukti")
        locked.evidence = evidence
        locked.result = result
        locked.completed_at = timezone.now()
    if target == ImprovementAction.Status.ACCEPTED_RISK:
        if not reason.strip():
            raise ValidationError("Accepted risk memerlukan alasan")
        locked.accepted_risk_reason = reason
    if target == ImprovementAction.Status.REOPENED:
        if not reason.strip():
            raise ValidationError("Reopen memerlukan alasan")
        locked.reopened_count += 1
    before = locked.status
    locked.status = target
    locked.updated_by_actor_id = str(user.pk)
    locked.full_clean()
    locked.save()
    record_change(
        actor=_actor(user),
        action="quality.action.transition",
        object_type="improvement-action",
        object_id=str(locked.public_id),
        summary="Status tindakan CQI diperbarui",
        before={"status": before},
        after={"status": target},
        reason=reason,
    )
    return locked


@transaction.atomic
def evaluate_action_effectiveness(
    action: ImprovementAction, *, current_actual: Decimal, evidence: list[dict], user
) -> ImprovementAction:
    locked = ImprovementAction.objects.select_for_update().get(pk=action.pk)
    if locked.status != ImprovementAction.Status.COMPLETED or not evidence:
        raise ValidationError("Evaluasi efektivitas memerlukan tindakan completed dan bukti")
    target = Decimal(str(locked.baseline["target"]))
    locked.result = {
        **locked.result,
        "current_actual": str(current_actual),
        "target": str(target),
        "effective": current_actual >= target,
        "evaluation_evidence": evidence,
    }
    locked.status = (
        ImprovementAction.Status.EFFECTIVE
        if current_actual >= target
        else ImprovementAction.Status.INEFFECTIVE
    )
    locked.evaluated_at = timezone.now()
    locked.updated_by_actor_id = str(user.pk)
    locked.full_clean()
    locked.save()
    return locked


def _report_package(
    *,
    cycle: QualityCycle,
    version: int,
    sections: dict[str, Any],
    source_versions: dict[str, Any],
    missing: list[str],
) -> dict[str, Any]:
    return {
        "contract": "obe-quality-report/1",
        "cycle": str(cycle.public_id),
        "period": cycle.period,
        "scope": {"type": cycle.scope_type, "id": cycle.scope_id},
        "version": version,
        "sections": sections,
        "source_versions": source_versions,
        "missing_sections": sorted(missing),
    }


@transaction.atomic
def generate_quality_report(
    *,
    cycle: QualityCycle,
    sections: dict[str, Any],
    source_versions: dict[str, Any],
    user,
    evaluation_type: str = "formative",
    correction_of: QualityReport | None = None,
) -> QualityReport:
    require_permission(user, "quality.report.generate")
    if evaluation_type not in {"formative", "summative"}:
        raise ValidationError("Jenis evaluasi harus formative atau summative")
    missing = sorted(key for key in REQUIRED_REPORT_SECTIONS if not sections.get(key))
    version = (
        QualityReport.objects.filter(
            period=cycle.period, scope_type=cycle.scope_type, scope_id=cycle.scope_id
        )
        .order_by("-version")
        .values_list("version", flat=True)
        .first()
        or 0
    ) + 1
    package = _report_package(
        cycle=cycle,
        version=version,
        sections=sections,
        source_versions=source_versions,
        missing=missing,
    )
    report = QualityReport(
        cycle=cycle,
        period=cycle.period,
        scope_type=cycle.scope_type,
        scope_id=cycle.scope_id,
        evaluation_type=evaluation_type,
        sections=sections,
        source_versions=source_versions,
        missing_sections=missing,
        package_checksum=_checksum(package),
        generated_by=user,
        correction_of=correction_of,
        version=version,
        created_by_actor_id=str(user.pk),
        updated_by_actor_id=str(user.pk),
    )
    report.full_clean()
    report.save()
    return report


@transaction.atomic
def transition_quality_report(
    report: QualityReport, *, target: str, user, note: str = ""
) -> QualityReport:
    locked = QualityReport.objects.select_for_update().get(pk=report.pk)
    if target not in REPORT_TRANSITIONS.get(locked.status, set()):
        raise ValidationError(f"Transisi laporan {locked.status} -> {target} tidak valid")
    permissions: dict[str, str] = {
        str(QualityReport.Status.GPM_REVIEWED): "quality.report.review",
        str(QualityReport.Status.PRODI_APPROVED): "quality.report.approve",
        str(QualityReport.Status.TPMF_REVIEWED): "quality.report.tpmf-review",
        str(QualityReport.Status.PUBLISHED): "quality.release",
        str(QualityReport.Status.CORRECTION): "quality.report.generate",
    }
    permission = permissions[target]
    require_permission(user, permission, scope_type=locked.scope_type, scope_id=locked.scope_id)
    if target == QualityReport.Status.GPM_REVIEWED:
        if user.pk == locked.generated_by_id:
            raise ValidationError("Pembuat laporan tidak boleh menjadi reviewer GPM")
        locked.reviewed_by = user
    elif target == QualityReport.Status.PRODI_APPROVED:
        if not locked.reviewed_by_id or user.pk in {locked.generated_by_id, locked.reviewed_by_id}:
            raise ValidationError("Approval Prodi memerlukan aktor terpisah")
        if locked.missing_sections:
            raise ValidationError("Laporan masih memiliki bagian yang hilang")
        locked.approved_by = user
    elif target == QualityReport.Status.TPMF_REVIEWED:
        if not locked.approved_by_id or user.pk in {
            locked.generated_by_id,
            locked.reviewed_by_id,
            locked.approved_by_id,
        }:
            raise ValidationError("TPMF reviewer harus aktor keempat yang berbeda")
        locked.tpmf_reviewer = user
    elif target == QualityReport.Status.PUBLISHED:
        if not locked.tpmf_reviewer_id:
            raise ValidationError("Review TPMF belum lengkap")
        locked.published_at = timezone.now()
    elif target == QualityReport.Status.CORRECTION and not note.strip():
        raise ValidationError("Correction cycle memerlukan alasan")
    locked.approval_history = [
        *locked.approval_history,
        {
            "from": locked.status,
            "to": target,
            "actor": str(user.pk),
            "at": timezone.now().isoformat(),
            "note": note,
        },
    ]
    before = locked.status
    locked.status = target
    locked.updated_by_actor_id = str(user.pk)
    locked.full_clean()
    locked.save()
    record_change(
        actor=_actor(user),
        action="quality.report.transition",
        object_type="quality-report",
        object_id=str(locked.public_id),
        summary="Workflow laporan PPEPP diperbarui",
        before={"status": before},
        after={"status": target},
        reason=note,
    )
    return locked


def export_quality_report(report: QualityReport, *, export_format: str) -> ExportArtifact:
    if report.status != QualityReport.Status.PUBLISHED:
        raise ValidationError("Export resmi hanya untuk laporan published")
    payload = _report_package(
        cycle=report.cycle,
        version=report.version,
        sections=report.sections,
        source_versions=report.source_versions,
        missing=report.missing_sections,
    )
    if _checksum(payload) != report.package_checksum:
        raise ValidationError("Checksum laporan mutu tidak cocok")
    basename = f"quality-report-{report.period}-{report.scope_id}-v{report.version}"
    if export_format == "json":
        content = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode()
        mime = "application/json"
    elif export_format == "html":
        content = (
            "<!doctype html><meta charset='utf-8'><title>OBE Quality Report</title><pre>"
            + html.escape(json.dumps(payload, ensure_ascii=False, indent=2))
            + "</pre>"
        ).encode()
        mime = "text/html; charset=utf-8"
    elif export_format == "pdf":
        content = _minimal_pdf(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        mime = "application/pdf"
    else:
        raise ValidationError("Format laporan harus json, html, atau pdf")
    return ExportArtifact(
        content, mime, hashlib.sha256(content).hexdigest(), f"{basename}.{export_format}"
    )


@transaction.atomic
def submit_academic_feedback(
    *,
    reporter,
    anonymous: bool,
    retaliation_risk: bool,
    period: str,
    course_offering_id: str,
    category: str,
    description: str,
    evidence: list[dict[str, Any]],
    impact: str,
) -> AcademicFeedback:
    require_permission(reporter, "feedback.submit")
    normalized = {
        "period": period.strip(),
        "course_offering_id": course_offering_id.strip(),
        "category": category.strip().lower(),
        "description": " ".join(description.split()),
        "impact": " ".join(impact.split()),
    }
    fingerprint = _checksum(normalized)
    duplicate = AcademicFeedback.objects.filter(fingerprint=fingerprint).exclude(
        status__in=[AcademicFeedback.Status.REJECTED, AcademicFeedback.Status.CLOSED]
    )
    if duplicate.exists():
        raise ValidationError("Masukan duplikat masih dalam penanganan")
    reporter_fingerprint = hashlib.sha256(
        f"{settings.SECRET_KEY}:{reporter.pk}".encode()
    ).hexdigest()
    row = AcademicFeedback(
        reporter=None if anonymous else reporter,
        reporter_fingerprint=reporter_fingerprint,
        anonymous=anonymous,
        retaliation_risk=retaliation_risk,
        confidentiality="restricted" if retaliation_risk else "internal",
        period=normalized["period"],
        course_offering_id=normalized["course_offering_id"],
        category=normalized["category"],
        description=normalized["description"],
        evidence=evidence,
        impact=normalized["impact"],
        fingerprint=fingerprint,
        created_by_actor_id="anonymous" if anonymous else str(reporter.pk),
        updated_by_actor_id="anonymous" if anonymous else str(reporter.pk),
    )
    row.full_clean()
    row.save()
    record_change(
        actor=ActorContext(
            "anonymous" if anonymous else str(reporter.pk),
            "Anonymous" if anonymous else reporter.get_username(),
            "feedback",
        ),
        action="feedback.submitted",
        object_type="academic-feedback",
        object_id=str(row.public_id),
        summary="Masukan akademik diterima",
        after={"category": row.category, "anonymous": anonymous},
    )
    return row


@transaction.atomic
def transition_academic_feedback(
    feedback: AcademicFeedback,
    *,
    target: str,
    user,
    reason: str,
    responsible=None,
    due_at=None,
    linked_objects: list[dict[str, Any]] | None = None,
    closure_evidence: list[dict[str, Any]] | None = None,
) -> AcademicFeedback:
    locked = AcademicFeedback.objects.select_for_update().get(pk=feedback.pk)
    if target not in FEEDBACK_TRANSITIONS.get(locked.status, set()):
        raise ValidationError(f"Transisi feedback {locked.status} -> {target} tidak valid")
    require_permission(user, "feedback.review")
    if target in {AcademicFeedback.Status.REJECTED, AcademicFeedback.Status.REOPENED}:
        if not reason.strip():
            raise ValidationError("Keputusan feedback memerlukan alasan")
    if target == AcademicFeedback.Status.VERIFIED and not (linked_objects or locked.linked_objects):
        raise ValidationError("Feedback verified harus ditautkan ke objek mutu")
    if target == AcademicFeedback.Status.ACTION_PLANNED:
        if responsible is None or due_at is None:
            raise ValidationError("Rencana tindak lanjut memerlukan owner dan deadline")
        locked.responsible = responsible
        locked.due_at = due_at
    if target == AcademicFeedback.Status.CLOSED:
        if not closure_evidence:
            raise ValidationError("Penutupan feedback memerlukan bukti")
        locked.closure_evidence = closure_evidence
    if linked_objects is not None:
        locked.linked_objects = linked_objects
    locked.decision_reason = reason
    before = locked.status
    locked.status = target
    locked.updated_by_actor_id = str(user.pk)
    locked.full_clean()
    locked.save()
    record_change(
        actor=_actor(user, "feedback"),
        action="feedback.transition",
        object_type="academic-feedback",
        object_id=str(locked.public_id),
        summary="Workflow masukan akademik diperbarui",
        before={"status": before},
        after={"status": target},
        reason=reason,
    )
    return locked


def feedback_payload_for(feedback: AcademicFeedback, *, user) -> dict[str, Any]:
    is_reporter = feedback.reporter_id == user.pk
    can_review = can(user, "feedback.review")
    is_responsible = feedback.responsible_id == user.pk
    if not (is_reporter or can_review or is_responsible):
        raise PermissionDenied("Akses kasus feedback ditolak")
    if feedback.confidentiality == "restricted" and not can_review and not is_reporter:
        raise PermissionDenied("Kasus restricted hanya untuk reviewer terotorisasi")
    record_change(
        actor=_actor(user, "feedback"),
        action="feedback.accessed",
        object_type="academic-feedback",
        object_id=str(feedback.public_id),
        summary="Kasus feedback dibuka oleh aktor terotorisasi",
    )
    return {
        "public_id": str(feedback.public_id),
        "anonymous": feedback.anonymous,
        "reporter": None if feedback.anonymous else feedback.reporter.get_username(),
        "period": feedback.period,
        "course_offering_id": feedback.course_offering_id,
        "category": feedback.category,
        "description": feedback.description,
        "evidence": feedback.evidence,
        "impact": feedback.impact,
        "confidentiality": feedback.confidentiality,
        "status": feedback.status,
        "responsible": str(feedback.responsible_id or ""),
        "due_at": feedback.due_at.isoformat() if feedback.due_at else None,
        "linked_objects": feedback.linked_objects,
        "closure_evidence": feedback.closure_evidence,
    }
