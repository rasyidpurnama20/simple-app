from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse
from django.utils import timezone

from obe.assessment.models import AttainmentFormula, AttainmentSnapshot
from obe.assessment.selectors import attainment_trace
from obe.assessment.services import (
    activate_attainment_formula,
    calculate_attainment,
    create_attainment_formula,
    review_attainment_formula,
)
from obe.identity.models import RoleAssignment
from obe.identity.services import ensure_demo_assignments
from obe.quality.models import (
    AcademicFeedback,
    ImprovementAction,
    PortfolioSnapshot,
    QualityCycle,
    QualityReport,
    QualityStandard,
)
from obe.quality.services import (
    evaluate_action_effectiveness,
    evaluate_provus,
    export_portfolio,
    export_quality_report,
    feedback_payload_for,
    generate_portfolio,
    generate_quality_report,
    plan_improvement_action,
    submit_academic_feedback,
    transition_academic_feedback,
    transition_improvement_action,
    transition_portfolio,
    transition_quality_report,
)
from obe.shared.models import AuditEvent


@pytest.fixture
def actors(monkeypatch):
    monkeypatch.setenv("OBE_DEMO_PASSWORD", "stage5-runtime-password")
    return ensure_demo_assignments()


def chain(suffix: str) -> dict[str, str]:
    return {
        "pl": "PL01",
        "cpl": "CPL01",
        "cpmk_program": "CPMK01",
        "cpmk_rps": "CPMK-RPS01",
        "sub_cpmk": f"SUB-{suffix}",
        "indicator": f"IND-{suffix}",
        "item": f"ITEM-{suffix}",
        "criterion": f"CRIT-{suffix}",
        "instrument": f"INST-{suffix}",
    }


def distribution() -> list[dict]:
    return [
        {"source_id": "SCORE-1", "weight": "60", "path": chain("1")},
        {"source_id": "SCORE-2", "weight": "40", "path": chain("2")},
    ]


def inputs(*, first="80", second="90", evidence_status="verified") -> list[dict]:
    return [
        {
            "source_id": "SCORE-1",
            "score_value": first,
            "max_score": "100",
            "path": chain("1"),
            "evidence_status": evidence_status,
            "score_status": "published",
            "source_versions": {"score": 1, "rubric": 2, "evidence": 1},
        },
        {
            "source_id": "SCORE-2",
            "score_value": second,
            "max_score": "100",
            "path": chain("2"),
            "evidence_status": "verified",
            "score_status": "published",
            "source_versions": {"score": 1, "rubric": 2, "evidence": 1},
        },
    ]


def verified_portfolio_sources() -> dict[str, list[dict]]:
    return {
        "rps": [{"id": "RPS-1", "status": "active"}],
        "assessments": [{"id": "INST-1", "status": "approved"}],
        "scores": [{"id": "SCORE-SUMMARY-1", "status": "published"}],
    }


def active_formula(actors, *, code="CPL01-COURSE", scope_type="course"):
    formula = create_attainment_formula(
        code=code,
        scope_type=scope_type,
        distribution=distribution(),
        target=Decimal("75"),
        source_versions={"curriculum": 1, "rps": 3, "assessment": 2, "rule": 1},
        user=actors["pengampu"],
    )
    formula = review_attainment_formula(formula, user=actors["gpm"])
    return activate_attainment_formula(formula, user=actors["prodi"])


@pytest.mark.django_db(transaction=True)
def test_pr34_formula_calculation_recalculation_and_fail_closed(actors):
    formula = active_formula(actors)
    snapshot = calculate_attainment(
        formula=formula,
        scope_id="OFF-IF-01",
        outcome_code="CPL01",
        inputs=inputs(),
        user=actors["pengampu"],
    )
    assert snapshot.actual == Decimal("84.00")
    assert snapshot.target == Decimal("75")
    assert snapshot.denominator == 2
    assert snapshot.coverage == Decimal("100.00")
    assert snapshot.status == AttainmentSnapshot.Status.VALID
    assert snapshot.contributions.count() == 2
    assert snapshot.source_checksum and len(snapshot.source_checksum) == 64

    formula_v2 = active_formula(actors)
    assert formula_v2.version == 2
    recalculated = calculate_attainment(
        formula=formula_v2,
        scope_id="OFF-IF-01",
        outcome_code="CPL01",
        inputs=inputs(first="90", second="90"),
        user=actors["pengampu"],
        previous_snapshot=snapshot,
        reason="Moderasi nilai dengan formula versi baru",
    )
    snapshot.refresh_from_db()
    assert snapshot.status == AttainmentSnapshot.Status.SUPERSEDED
    assert recalculated.snapshot_version == 2
    assert recalculated.actual == Decimal("90.00")
    assert recalculated.difference["actual_before"] == "84.00"
    assert recalculated.difference["formula_before"] != recalculated.difference["formula_after"]

    blocked = calculate_attainment(
        formula=formula_v2,
        scope_id="OFF-IF-02",
        outcome_code="CPL01",
        inputs=inputs(evidence_status="submitted")[:1],
        user=actors["pengampu"],
        external_blocking_reasons=["INTEGRITY_ISSUE_OPEN"],
    )
    assert blocked.actual is None
    assert blocked.status == AttainmentSnapshot.Status.BLOCKED
    assert blocked.denominator == 0
    assert blocked.coverage == 0
    assert {
        "EVIDENCE_NOT_VERIFIED",
        "MISSING_SOURCE",
        "INTEGRITY_ISSUE_OPEN",
    } <= set(blocked.blocking_reasons)
    with pytest.raises(ValidationError, match="alasan"):
        calculate_attainment(
            formula=formula_v2,
            scope_id="OFF-IF-01",
            outcome_code="CPL01",
            inputs=inputs(),
            user=actors["pengampu"],
            previous_snapshot=recalculated,
        )


@pytest.mark.django_db(transaction=True)
def test_pr34_formula_validation_and_separation_of_duties(actors):
    invalid = AttainmentFormula(
        code="INVALID",
        scope_type="course",
        distribution=[{"source_id": "A", "weight": 90, "path": chain("A")}],
        created_by=actors["pengampu"],
    )
    with pytest.raises(ValidationError, match="100"):
        invalid.full_clean()
    formula = create_attainment_formula(
        code="SOD",
        scope_type="program",
        distribution=distribution(),
        target=Decimal("75"),
        source_versions={},
        user=actors["pengampu"],
    )
    with pytest.raises(ValidationError, match="reviewer"):
        review_attainment_formula(formula, user=actors["pengampu"])
    reviewed = review_attainment_formula(formula, user=actors["gpm"])
    with pytest.raises(ValidationError, match="Approver"):
        activate_attainment_formula(reviewed, user=actors["gpm"])


@pytest.mark.django_db(transaction=True)
def test_pr35_forward_backward_trace_keeps_gaps_and_permissions(client, actors):
    formula = active_formula(actors, code="TRACE")
    snapshot = calculate_attainment(
        formula=formula,
        scope_id="OFF-TRACE",
        outcome_code="CPL01",
        inputs=inputs(),
        user=actors["pengampu"],
    )
    forward = attainment_trace(snapshot.id)
    backward = attainment_trace(snapshot.id, direction="backward", start=str(snapshot.id))
    assert forward["nodes"] and forward["edges"]
    assert "TRACE_GAP_VISIBLE" in forward["warnings"]
    assert any(node["type"] == "course" and node["gate"] == "learning" for node in forward["nodes"])
    assert any(node["type"] == "evidence" and node["status"] == "gap" for node in forward["nodes"])
    assert any(node["type"] == "cqi" and node["status"] == "gap" for node in forward["nodes"])
    assert {edge["gate"] for edge in forward["edges"]} >= {
        "curriculum",
        "learning",
        "assessment",
        "attainment",
        "cqi",
    }
    assert backward["nodes"] and backward["edges"]
    first_forward = forward["edges"][0]
    assert any(
        edge["source"] == first_forward["target"] and edge["target"] == first_forward["source"]
        for edge in attainment_trace(snapshot.id, direction="backward")["edges"]
    )

    client.force_login(actors["mahasiswa"])
    response = client.get(reverse("attainment-trace", args=[snapshot.id]), {"direction": "forward"})
    assert response.status_code == 200
    assert response.json()["schema_version"] == "obe-trace/1"
    outsider = get_user_model().objects.create_user("trace-outsider")
    client.force_login(outsider)
    assert client.get(reverse("attainment-trace", args=[snapshot.id])).status_code == 403


@pytest.mark.django_db(transaction=True)
def test_pr36_portfolio_lifecycle_reproducible_export_and_regeneration(client, actors):
    formula = active_formula(actors, code="PORTFOLIO")
    calculate_attainment(
        formula=formula,
        scope_id="OFF-PORT",
        outcome_code="CPL01",
        inputs=inputs(),
        user=actors["pengampu"],
    )
    portfolio = generate_portfolio(
        portfolio_type="course",
        scope_id="OFF-PORT",
        period="2025-1",
        evidence=[{"manifest_id": "MAN-1", "status": "verified", "sha256": "a" * 64}],
        findings=[{"id": "F-1", "status": "closed"}],
        actions=[{"id": "A-1", "status": "effective"}],
        source_versions={"dataset": "5.0.0", "curriculum": 1},
        user=actors["pengampu"],
        **verified_portfolio_sources(),
    )
    assert portfolio.status == PortfolioSnapshot.Status.DRAFT
    assert portfolio.incomplete_sections == []
    assert set(portfolio.sections) >= {"rps", "assessments", "scores", "attainment"}
    assert len(portfolio.package_checksum) == 64
    portfolio = transition_portfolio(
        portfolio, target=PortfolioSnapshot.Status.GPM_REVIEW, user=actors["gpm"]
    )
    with pytest.raises(PermissionDenied):
        transition_portfolio(
            portfolio, target=PortfolioSnapshot.Status.APPROVED, user=actors["gpm"]
        )
    portfolio = transition_portfolio(
        portfolio, target=PortfolioSnapshot.Status.APPROVED, user=actors["prodi"]
    )
    portfolio = transition_portfolio(
        portfolio, target=PortfolioSnapshot.Status.PUBLISHED, user=actors["prodi"]
    )
    artifacts = {
        fmt: export_portfolio(portfolio, export_format=fmt) for fmt in ("html", "csv", "pdf")
    }
    assert artifacts["html"].content.startswith(b"<!doctype html>")
    assert artifacts["csv"].content.startswith(b"outcome,actual,target")
    assert artifacts["pdf"].content.startswith(b"%PDF-1.4")
    assert all(len(artifact.checksum) == 64 for artifact in artifacts.values())

    client.force_login(actors["gpm"])
    response = client.get(reverse("portfolio-detail", args=[portfolio.public_id]))
    assert response.status_code == 200
    assert response.json()["package_checksum"] == portfolio.package_checksum

    replacement = generate_portfolio(
        portfolio_type="course",
        scope_id="OFF-PORT",
        period="2025-1",
        evidence=[{"manifest_id": "MAN-1", "status": "verified"}],
        findings=[{"id": "F-1", "status": "closed"}],
        actions=[{"id": "A-1", "status": "effective"}],
        source_versions={"dataset": "5.0.0", "curriculum": 1},
        user=actors["pengampu"],
        supersedes=portfolio,
        **verified_portfolio_sources(),
    )
    portfolio.refresh_from_db()
    assert replacement.version == 2
    assert portfolio.status == PortfolioSnapshot.Status.SUPERSEDED

    incomplete = generate_portfolio(
        portfolio_type="program",
        scope_id="NO-DATA",
        period="2025-1",
        evidence=[{"manifest_id": "MAN-X", "status": "submitted"}],
        findings=[],
        actions=[],
        source_versions={},
        user=actors["gpm"],
    )
    incomplete = transition_portfolio(
        incomplete, target=PortfolioSnapshot.Status.GPM_REVIEW, user=actors["gpm"]
    )
    with pytest.raises(ValidationError, match="maker-checker|lengkap"):
        transition_portfolio(
            incomplete, target=PortfolioSnapshot.Status.APPROVED, user=actors["prodi"]
        )


@pytest.mark.django_db(transaction=True)
def test_pr37_provus_cqi_effectiveness_ineffective_risk_and_api(client, actors):
    formula = active_formula(actors, code="PROVUS")
    snapshot = calculate_attainment(
        formula=formula,
        scope_id="OFF-CQI",
        outcome_code="CPL01",
        inputs=inputs(first="70", second="70"),
        user=actors["pengampu"],
    )
    QualityStandard.objects.create(
        source_id="STD-CPL01",
        code="STD-CPL01",
        metric="CPL01",
        target=75,
        created_by_actor_id=str(actors["gpm"].pk),
        updated_by_actor_id=str(actors["gpm"].pk),
    )
    findings = evaluate_provus(
        period="2025-1",
        attainment_rows=[
            {
                "metric": "CPL01",
                "scope_type": "course",
                "scope_id": "OFF-CQI",
                "actual": "70",
                "denominator": 30,
                "coverage": "95",
            },
            {
                "metric": "CPL01",
                "scope_type": "course",
                "scope_id": "OFF-CQI-MET",
                "actual": "75",
                "denominator": 24,
                "coverage": "80",
            },
            {
                "metric": "CPL01",
                "scope_type": "course",
                "scope_id": "OFF-CQI-EXCEEDED",
                "actual": "82",
                "denominator": 18,
                "coverage": "60",
            },
        ],
        user=actors["gpm"],
    )
    finding = findings[0]
    assert finding.classification == "below"
    assert finding.gap == Decimal("-5")
    assert finding.confidence == "high"
    assert [(row.classification, row.confidence) for row in findings[1:]] == [
        ("met", "medium"),
        ("exceeded", "low"),
    ]
    action = plan_improvement_action(
        finding=finding,
        root_cause="Latihan formatif belum merata",
        action="Tambah klinik belajar mingguan",
        owner=actors["pengampu"],
        due_at=timezone.now() + timedelta(days=30),
        success_indicator="CPL01 minimal 75",
        user=actors["gpm"],
    )
    action = transition_improvement_action(
        action, target=ImprovementAction.Status.ACTIVE, user=actors["prodi"]
    )
    action = transition_improvement_action(
        action,
        target=ImprovementAction.Status.COMPLETED,
        user=actors["pengampu"],
        evidence=[{"manifest_id": "CQI-1", "status": "verified"}],
        result={"participants": 30},
    )
    action = evaluate_action_effectiveness(
        action,
        current_actual=Decimal("78"),
        evidence=[{"snapshot": "NEXT-1"}],
        user=actors["gpm"],
    )
    assert action.status == ImprovementAction.Status.EFFECTIVE

    action2 = plan_improvement_action(
        finding=finding,
        root_cause="Umpan balik terlambat",
        action="SLA feedback tujuh hari",
        owner=actors["pengampu"],
        due_at=timezone.now() + timedelta(days=20),
        success_indicator="CPL01 minimal 75",
        user=actors["gpm"],
    )
    action2 = transition_improvement_action(
        action2, target=ImprovementAction.Status.ACTIVE, user=actors["prodi"]
    )
    action2 = transition_improvement_action(
        action2,
        target=ImprovementAction.Status.COMPLETED,
        user=actors["pengampu"],
        evidence=[{"manifest_id": "CQI-2"}],
        result={"sla_days": 7},
    )
    action2 = evaluate_action_effectiveness(
        action2,
        current_actual=Decimal("72"),
        evidence=[{"snapshot": "NEXT-2"}],
        user=actors["gpm"],
    )
    assert action2.status == ImprovementAction.Status.INEFFECTIVE
    action2 = transition_improvement_action(
        action2,
        target=ImprovementAction.Status.REOPENED,
        user=actors["gpm"],
        reason="Target periode berikutnya belum tercapai",
    )
    assert action2.reopened_count == 1

    accepted_risk = plan_improvement_action(
        finding=finding,
        root_cause="Keterbatasan kapasitas laboratorium sementara",
        action="Pantau kapasitas sambil menunggu pengadaan",
        owner=actors["pengampu"],
        due_at=timezone.now() + timedelta(days=45),
        success_indicator="Risiko ditinjau pada siklus berikutnya",
        user=actors["gpm"],
    )
    accepted_risk = transition_improvement_action(
        accepted_risk,
        target=ImprovementAction.Status.ACCEPTED_RISK,
        user=actors["prodi"],
        reason="Risiko diterima satu siklus dengan mitigasi dan tenggat yang tercatat",
    )
    assert accepted_risk.accepted_risk_reason

    client.force_login(actors["prodi"])
    response = client.get(reverse("quality-finding-list"))
    assert response.status_code == 200
    assert response.json()["data"][0]["classification"] == "below"
    trace = client.get(reverse("attainment-trace", args=[snapshot.id]))
    assert trace.status_code == 200
    assert {node["status"] for node in trace.json()["nodes"] if node["type"] == "cqi-action"} >= {
        "effective",
        "reopened",
        "accepted-risk",
    }


def complete_report_sections():
    return {
        "rps": [{"count": 77}],
        "assessment": [{"count": 459}],
        "attendance": [{"coverage": 95}],
        "scores": [{"published": 366}],
        "attainment": [{"outcome": "CPL01", "actual": 78}],
        "evidence": [{"manifest": "MAN-1"}],
        "complaints": [{"count": 1}],
        "findings": [{"id": "F-1"}],
        "cqi": [{"id": "A-1"}],
        "effectiveness": [{"effective": True}],
    }


@pytest.mark.django_db(transaction=True)
def test_pr38_ppepp_report_four_actor_workflow_export_and_correction(client, actors):
    tpmf = get_user_model().objects.create_user("tpmf-stage5")
    RoleAssignment.objects.create(
        user=tpmf,
        role=RoleAssignment.Role.TPMF,
        scope_type="program",
        scope_id="S1-IF",
        period="2025-1",
        actions=["quality.report.tpmf-review", "quality.view"],
        granted_by=actors["prodi"],
    )
    cycle = QualityCycle.objects.create(
        period="2025-1",
        scope_type="program",
        scope_id="S1-IF",
        standard={"phase": "penetapan"},
        execution={"phase": "pelaksanaan"},
        evaluation={"phase": "evaluasi"},
        control={"phase": "pengendalian"},
        improvement={"phase": "peningkatan"},
        created_by_actor_id=str(actors["pengampu"].pk),
        updated_by_actor_id=str(actors["pengampu"].pk),
    )
    report = generate_quality_report(
        cycle=cycle,
        sections=complete_report_sections(),
        source_versions={"dataset": "5.0.0", "formula": "CPL01/1"},
        user=actors["pengampu"],
    )
    report = transition_quality_report(
        report, target=QualityReport.Status.GPM_REVIEWED, user=actors["gpm"]
    )
    report = transition_quality_report(
        report, target=QualityReport.Status.PRODI_APPROVED, user=actors["prodi"]
    )
    report = transition_quality_report(report, target=QualityReport.Status.TPMF_REVIEWED, user=tpmf)
    report = transition_quality_report(
        report, target=QualityReport.Status.PUBLISHED, user=actors["prodi"]
    )
    assert report.published_at
    assert len(report.approval_history) == 4
    for fmt in ("json", "html", "pdf"):
        artifact = export_quality_report(report, export_format=fmt)
        assert artifact.content and len(artifact.checksum) == 64

    client.force_login(actors["gpm"])
    response = client.get(reverse("quality-report", args=[report.public_id]))
    assert response.status_code == 200
    assert response.json()["status"] == "published"

    report = transition_quality_report(
        report,
        target=QualityReport.Status.CORRECTION,
        user=actors["pengampu"],
        note="Koreksi denominator setelah rekonsiliasi",
    )
    correction = generate_quality_report(
        cycle=cycle,
        sections=complete_report_sections(),
        source_versions={"dataset": "5.0.0", "formula": "CPL01/1"},
        user=actors["pengampu"],
        correction_of=report,
    )
    assert correction.version == 2
    assert correction.correction_of == report

    incomplete = generate_quality_report(
        cycle=cycle,
        sections={"rps": [{"count": 77}]},
        source_versions={},
        user=actors["pengampu"],
    )
    incomplete = transition_quality_report(
        incomplete, target=QualityReport.Status.GPM_REVIEWED, user=actors["gpm"]
    )
    with pytest.raises(ValidationError, match="bagian"):
        transition_quality_report(
            incomplete, target=QualityReport.Status.PRODI_APPROVED, user=actors["prodi"]
        )


@pytest.mark.django_db(transaction=True)
def test_pr39_feedback_anonymous_duplicate_restricted_lifecycle_and_audit(client, actors):
    feedback = submit_academic_feedback(
        reporter=actors["mahasiswa"],
        anonymous=True,
        retaliation_risk=True,
        period="2025-1",
        course_offering_id="OFF-IF-01",
        category="academic",
        description="Umpan balik asesmen belum konsisten",
        evidence=[{"manifest_id": "FB-1"}],
        impact="Mahasiswa tidak memahami kriteria keberhasilan",
    )
    assert feedback.reporter is None
    assert feedback.confidentiality == "restricted"
    with pytest.raises(ValidationError, match="duplikat"):
        submit_academic_feedback(
            reporter=actors["mahasiswa"],
            anonymous=True,
            retaliation_risk=True,
            period="2025-1",
            course_offering_id="OFF-IF-01",
            category="academic",
            description="Umpan balik asesmen belum konsisten",
            evidence=[],
            impact="Mahasiswa tidak memahami kriteria keberhasilan",
        )
    with pytest.raises(ValidationError, match="ditautkan"):
        transition_academic_feedback(
            feedback,
            target=AcademicFeedback.Status.VERIFIED,
            user=actors["gpm"],
            reason="Klaim didukung bukti",
        )
    feedback = transition_academic_feedback(
        feedback,
        target=AcademicFeedback.Status.VERIFIED,
        user=actors["gpm"],
        reason="Klaim didukung bukti",
        linked_objects=[{"type": "quality-cycle", "id": "2025-1"}],
    )
    feedback = transition_academic_feedback(
        feedback,
        target=AcademicFeedback.Status.ACTION_PLANNED,
        user=actors["gpm"],
        reason="Perlu kalibrasi rubrik",
        responsible=actors["pengampu"],
        due_at=timezone.now() + timedelta(days=14),
    )
    feedback = transition_academic_feedback(
        feedback,
        target=AcademicFeedback.Status.ACTIONED,
        user=actors["gpm"],
        reason="Kalibrasi selesai",
    )
    feedback = transition_academic_feedback(
        feedback,
        target=AcademicFeedback.Status.CLOSED,
        user=actors["gpm"],
        reason="Pelapor dan GPM memverifikasi tindak lanjut",
        closure_evidence=[{"manifest_id": "FB-CLOSE-1"}],
    )
    feedback = transition_academic_feedback(
        feedback,
        target=AcademicFeedback.Status.REOPENED,
        user=actors["gpm"],
        reason="Masalah terulang pada kelas paralel",
    )
    assert feedback.status == AcademicFeedback.Status.REOPENED
    payload = feedback_payload_for(feedback, user=actors["gpm"])
    assert payload["reporter"] is None
    assert payload["linked_objects"]
    with pytest.raises(PermissionDenied):
        feedback_payload_for(feedback, user=actors["pengampu"])
    assert (
        AuditEvent.objects.filter(
            object_type="academic-feedback", object_id=str(feedback.public_id)
        ).count()
        >= 7
    )

    client.force_login(actors["mahasiswa"])
    response = client.post(
        reverse("academic-feedback"),
        {
            "anonymous": False,
            "period": "2025-1",
            "course_offering_id": "OFF-IF-02",
            "category": "nonacademic",
            "description": "Jadwal konsultasi berubah tanpa pemberitahuan",
            "evidence": [],
            "impact": "Mahasiswa kehilangan sesi konsultasi",
        },
        content_type="application/json",
    )
    assert response.status_code == 201
    own = AcademicFeedback.objects.get(public_id=response.json()["public_id"])
    detail = client.get(reverse("academic-feedback-detail", args=[own.public_id]))
    assert detail.status_code == 200
    assert detail.json()["reporter"] == "mahasiswa"
