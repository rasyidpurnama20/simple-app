from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, connection, transaction
from django.http import HttpResponse
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone

from obe.identity.models import AccountSecurity, RoleAssignment
from obe.identity.permissions import (
    ScopedActionPermission,
    deny_direct_object_access,
    require_action,
    require_distinct_approver,
)
from obe.identity.services import (
    authorize,
    can,
    decision_dict,
    grant_assignment,
    issue_mfa_challenge,
    permission_snapshot,
    provision_user,
    register_login_failure,
    register_login_success,
    revoke_assignment,
    validate_permission_snapshot,
    verify_mfa_challenge,
)
from obe.shared.audit import (
    export_audit,
    purge_expired_sensitive_payloads,
    search_audit,
    verify_audit_chain,
    verify_signed_export,
)
from obe.shared.feature_flags import (
    FlagContext,
    create_flag,
    evaluate_flag,
    flag_snapshot,
    transition_flag,
    validate_flag_snapshot,
)
from obe.shared.jobs import create_job, execute_job
from obe.shared.models import AuditEvent, AuditSensitivePayload, FeatureFlag
from obe.shared.security import (
    isolated_upload_name,
    safe_redirect_target,
    validate_outbound_url,
)
from obe.shared.services import ActorContext, record_change

ROOT = Path(__file__).resolve().parents[1]


def assigned_user(username: str, *actions: str, role: str = "prodi"):
    User = get_user_model()
    user = User.objects.create_user(username=username, password="valid-test-password")
    granter = User.objects.create_user(username=f"grant-{username}")
    RoleAssignment.objects.create(
        user=user,
        role=role,
        scope_type="global",
        scope_id="*",
        actions=list(actions),
        granted_by=granter,
    )
    return user


@pytest.mark.django_db
def test_pr11_security_headers_rate_limit_and_admin_network_boundary(client):
    cache.clear()
    response = client.get(reverse("healthz"))
    assert response["Content-Security-Policy"].startswith("default-src 'self'")
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert response["X-Frame-Options"] == "DENY"
    assert response["Cross-Origin-Opener-Policy"] == "same-origin"

    denied = client.get("/admin/", REMOTE_ADDR="203.0.113.9")
    assert denied.status_code == 403
    for _ in range(5):
        assert client.get(reverse("login"), REMOTE_ADDR="198.51.100.7").status_code == 200
    limited = client.get(reverse("login"), REMOTE_ADDR="198.51.100.7")
    assert limited.status_code == 429 and limited["Retry-After"] == "300"


def test_pr11_safe_redirect_ssrf_and_upload_path_guards(monkeypatch):
    assert (
        safe_redirect_target(
            "https://obe.example.invalid/catalog/",
            allowed_hosts={"obe.example.invalid"},
            require_https=True,
        )
        == "https://obe.example.invalid/catalog/"
    )
    assert (
        safe_redirect_target(
            "https://evil.example/", allowed_hosts={"obe.example.invalid"}, require_https=True
        )
        == "/"
    )
    monkeypatch.setattr(
        "socket.getaddrinfo",
        lambda *_args: [(2, 1, 6, "", ("127.0.0.1", 443))],
    )
    with pytest.raises(ValueError, match="private/reserved"):
        validate_outbound_url(
            "https://gateway.example.invalid/v1",
            allowed_hosts={"gateway.example.invalid"},
        )
    assert (
        isolated_upload_name("../../evidence/report.pdf", allowed_extensions={".pdf"})
        == "report.pdf"
    )
    with pytest.raises(ValueError):
        isolated_upload_name("payload.svg", allowed_extensions={".pdf"})


def test_pr11_deployment_has_deny_by_default_zones_and_no_private_ports():
    compose = yaml.safe_load((ROOT / "deploy/server/compose.yml").read_text(encoding="utf-8"))
    assert set(compose["networks"]) == {
        "public",
        "application",
        "data",
        "telemetry",
        "ai",
        "administration",
        "exam-edge",
    }
    assert all(
        config.get("internal") is True
        for name, config in compose["networks"].items()
        if name != "public"
    )
    assert compose["services"]["proxy"]["ports"] == ["443:443"]
    assert all(
        "ports" not in service for name, service in compose["services"].items() if name != "proxy"
    )
    assert "ai" in compose["services"]["worker-ai"]["networks"]
    assert "exam-edge" in compose["services"]["worker-sync"]["networks"]
    nginx = (ROOT / "deploy/server/nginx.conf").read_text(encoding="utf-8")
    for control in ("Strict-Transport-Security", "Content-Security-Policy", "deny all"):
        assert control in nginx


@pytest.mark.django_db
def test_pr12_account_lock_and_one_time_mfa_challenge(settings):
    user = get_user_model().objects.create_user("locked-user")
    settings.OBE_LOGIN_LOCK_THRESHOLD = 3
    for _ in range(3):
        profile = register_login_failure(user, ip_address="192.0.2.10")
    assert profile.locked
    with pytest.raises(PermissionDenied):
        register_login_success(user)

    AccountSecurity.objects.filter(user=user).update(
        locked_until=timezone.now() - timedelta(seconds=1)
    )
    profile = register_login_success(user)
    profile.mfa_enabled = True
    profile.mfa_enrolled_at = timezone.now()
    profile.save(update_fields=["mfa_enabled", "mfa_enrolled_at", "updated_at"])
    challenge, token = issue_mfa_challenge(user)
    assert verify_mfa_challenge(challenge.pk, token, user=user)
    assert not verify_mfa_challenge(challenge.pk, token, user=user)


@pytest.mark.django_db
def test_pr12_login_mfa_and_session_revocation(client):
    cache.clear()
    user = get_user_model().objects.create_user(
        "mfa-user", email="mfa@example.invalid", password="valid-test-password"
    )
    AccountSecurity.objects.create(
        user=user,
        mfa_enabled=True,
        mfa_enrolled_at=timezone.now(),
    )
    response = client.post(
        reverse("login"),
        {"username": "mfa-user", "password": "valid-test-password"},
        REMOTE_ADDR="192.0.2.11",
    )
    assert response.status_code == 302 and response.url == reverse("mfa-verify")
    token = mail.outbox[0].body.rsplit(": ", 1)[1]
    verified = client.post(reverse("mfa-verify"), {"token": token}, REMOTE_ADDR="192.0.2.11")
    assert verified.status_code == 302 and verified.url == reverse("dashboard")
    assert client.get(reverse("dashboard")).status_code == 200

    AccountSecurity.objects.filter(user=user).update(permission_epoch=2)
    revoked = client.get(reverse("dashboard"))
    assert revoked.status_code == 401 and revoked.json()["error"]["code"] == "session_revoked"


@pytest.mark.django_db
def test_pr12_scoped_permission_prevents_idor_and_expired_assignment():
    student = assigned_user("student-1", "task.view", role="mahasiswa")
    assert can(
        student,
        "task.view",
        scope_type="student",
        scope_id=str(student.pk),
        owner_id=str(student.pk),
    )
    assert not can(student, "task.view", scope_type="student", scope_id="other", owner_id="other")
    assignment = RoleAssignment.objects.get(user=student)
    assignment.expires_at = timezone.now() - timedelta(seconds=1)
    assignment.save(update_fields=["expires_at", "updated_at"])
    assert not can(student, "task.view", scope_type="student", scope_id=str(student.pk))


@pytest.mark.django_db
def test_pr12_assignment_revocation_invalidates_permission_and_background_job():
    manager = assigned_user("permission-manager", "assignment.manage")
    worker = get_user_model().objects.create_user("scoped-worker")
    assignment = grant_assignment(
        granter=manager,
        user=worker,
        role="pengampu",
        scope_type="course",
        scope_id="IF101",
        actions=["report.generate"],
        period="2026-odd",
    )
    snapshot = permission_snapshot(
        worker,
        "report.generate",
        scope_type="course",
        scope_id="IF101",
        period="2026-odd",
    )
    assert validate_permission_snapshot(snapshot)
    job, _ = create_job(
        task_name="reports.secure",
        queue="reports",
        idempotency_key="reports:secure:1",
        payload={"course": "IF101"},
        authorization_snapshot=snapshot,
    )
    revoke_assignment(assignment=assignment, actor=manager, reason="teaching period ended")
    assert not validate_permission_snapshot(snapshot)
    outcome = execute_job(job.id, generation=1, operation=lambda _progress: {"created": True})
    assert outcome.status == "unauthorized"


@pytest.mark.django_db
def test_pr12_program_can_provision_users_but_self_approval_is_rejected():
    prodi = assigned_user("prodi-manager", "user.manage")
    user = provision_user(
        actor=prodi,
        username="new-lecturer",
        email="lecturer@example.invalid",
        scope_id="IF",
    )
    assert not user.has_usable_password()
    assert user.security_profile.password_reset_required
    with pytest.raises(ValidationError, match="Self-approval"):
        require_distinct_approver(maker_id="1", approver_id="1")


@pytest.mark.django_db
def test_pr12_permission_adapters_and_validation_fail_closed():
    user = assigned_user("adapter-user", "course.view", role="pengampu")
    request = RequestFactory().get("/course/IF101")
    request.user = user

    @require_action("course.view", scope_type="course", scope_kwarg="course_id")
    def protected(_request, course_id):
        return HttpResponse(course_id)

    assert protected(request, course_id="IF101").content == b"IF101"
    permission = ScopedActionPermission()
    view = SimpleNamespace(
        required_action="course.view",
        scope_type="course",
        scope_kwarg="course_id",
        kwargs={"course_id": "IF101"},
    )
    assert permission.has_permission(request, view)
    request.user = get_user_model().objects.create_user("adapter-denied")
    with pytest.raises(PermissionDenied):
        protected(request, course_id="IF101")
    assert not permission.has_permission(request, view)
    with pytest.raises(PermissionDenied):
        deny_direct_object_access()

    invalid = RoleAssignment(
        user=request.user,
        role="pengampu",
        actions=[],
        granted_by=user,
        expires_at=timezone.now() - timedelta(seconds=1),
    )
    with pytest.raises(ValidationError):
        invalid.full_clean()
    profile = AccountSecurity(user=request.user, mfa_enabled=True)
    with pytest.raises(ValidationError, match="MFA aktif"):
        profile.full_clean()
    with pytest.raises(ValidationError, match="MFA belum"):
        issue_mfa_challenge(request.user)
    assert validate_permission_snapshot({})
    assert decision_dict(authorize(user, "course.view"))["allowed"]


@pytest.mark.django_db
def test_pr12_login_failure_lock_logout_and_mfa_negative_paths(client):
    cache.clear()
    user = get_user_model().objects.create_user("auth-negative", password="valid-test-password")
    denied = client.post(
        reverse("login"),
        {"username": user.username, "password": "wrong-password"},
        REMOTE_ADDR="192.0.2.20",
    )
    assert denied.status_code == 200
    assert AuditEvent.objects.filter(action="identity.login", outcome="denied").exists()

    profile = user.security_profile
    profile.locked_until = timezone.now() + timedelta(minutes=5)
    profile.save(update_fields=["locked_until", "updated_at"])
    locked = client.post(
        reverse("login"),
        {"username": user.username, "password": "valid-test-password"},
        REMOTE_ADDR="192.0.2.20",
    )
    assert locked.status_code == 200
    assert AuditEvent.objects.filter(action="identity.login", outcome="locked").exists()

    profile.locked_until = timezone.now() - timedelta(seconds=1)
    profile.save(update_fields=["locked_until", "updated_at"])
    assert client.login(username=user.username, password="valid-test-password")
    assert client.post(reverse("logout"), REMOTE_ADDR="192.0.2.20").status_code == 302
    assert AuditEvent.objects.filter(action="identity.logout", outcome="success").exists()

    assert client.get(reverse("mfa-verify")).status_code == 302
    client.force_login(user)
    assert client.get(reverse("mfa-verify")).url == reverse("dashboard")
    session = client.session
    session["obe_mfa_challenge"] = 999999
    session.save()
    invalid = client.post(reverse("mfa-verify"), {"token": "invalid"})
    assert invalid.status_code == 200


@pytest.mark.django_db
def test_pr12_analytics_direct_url_requires_central_permission(client):
    user = get_user_model().objects.create_user("no-analytics")
    client.force_login(user)
    assert client.get(reverse("semantic-analytics"), {"metric": "attainment"}).status_code == 403
    granter = get_user_model().objects.create_user("analytics-granter")
    RoleAssignment.objects.create(
        user=user,
        role="gpm",
        actions=["analytics.view"],
        granted_by=granter,
    )
    assert client.get(reverse("semantic-analytics"), {"metric": "attainment"}).status_code == 200


@pytest.mark.django_db(transaction=True)
def test_pr13_audit_is_redacted_chained_append_only_and_tamper_evident():
    first = record_change(
        actor=ActorContext("prodi-1", "Prodi", "program:IF"),
        actor_role="prodi",
        assignment_reference="assignment-1",
        action="assessment.grade.changed",
        object_type="submission",
        object_id="SUB-1",
        summary="Grade changed with maker-checker",
        after={"raw_grade": 95, "status": "approved"},
        sensitive_payload={"student_number": "24001", "raw_grade": 95},
        reason="approved correction",
        references=(("decision", "DEC-1", "grade decision"),),
    )
    second = record_change(
        actor=ActorContext("gpm-1", "GPM"),
        action="quality.reviewed",
        object_type="submission",
        object_id="SUB-1",
        summary="Quality review completed",
    )
    assert first.after["raw_grade"] == "[redacted]"
    assert first.sensitive_payload.payload["student_number"] == "24001"
    assert first.references.get(source_id="DEC-1")
    assert second.previous_hash == first.integrity_hash
    assert verify_audit_chain()[0]
    with pytest.raises(ValidationError):
        AuditEvent.objects.filter(pk=first.pk).update(summary="tampered")
    with pytest.raises(DatabaseError):
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE shared_auditevent SET summary = %s WHERE id = %s",
                    ["tampered", first.id.hex],
                )


@pytest.mark.django_db
def test_pr13_reason_failed_transaction_search_signed_export_and_retention():
    with pytest.raises(ValidationError, match="alasan"):
        record_change(
            actor=ActorContext("prodi-1"),
            action="export.student",
            object_type="student",
            object_id="24001",
            summary="Export requested",
        )
    with pytest.raises(RuntimeError):
        with transaction.atomic():
            record_change(
                actor=ActorContext("prodi-1"),
                action="curriculum.changed",
                object_type="curriculum",
                object_id="IF-2026",
                summary="Will roll back",
            )
            raise RuntimeError("rollback")
    assert not AuditEvent.objects.filter(summary="Will roll back").exists()

    event = record_change(
        actor=ActorContext("system", "importer"),
        action="import.failed",
        object_type="dataset",
        object_id="sample-v5",
        summary="Import failed",
        reason="validation error",
        outcome="failed",
        sensitive_payload={"file_path": "/private/import.json"},
        retention_days=-1,
    )
    auditor = assigned_user("auditor", "audit.view", "audit.export", role="gpm")
    found = search_audit(user=auditor, action="import.failed")
    assert list(found) == [event]
    signed = export_audit(user=auditor, events=AuditEvent.objects.all())
    assert verify_signed_export(signed)
    tampered = type(signed)(signed.content + b"x", signed.sha256, signed.signature)
    assert not verify_signed_export(tampered)
    assert purge_expired_sensitive_payloads() == 1
    assert not AuditSensitivePayload.objects.filter(audit=event).exists()


@pytest.mark.django_db
def test_pr14_feature_flag_state_scope_permission_and_cache_invalidation():
    manager = assigned_user("flag-manager", "feature_flag.manage")
    pilot = assigned_user("pilot-user", "analytics.view", role="gpm")
    flag = create_flag(
        actor=manager,
        code="new-dashboard",
        owner="analytics-team",
        scope={"module": "analytics", "roles": ["gpm"], "environment": ["test"]},
    )
    context = FlagContext(
        environment="test",
        module="analytics",
        role="gpm",
        user_id=str(pilot.pk),
    )
    assert not evaluate_flag("new-dashboard", context=context).enabled
    enabled = transition_flag(
        flag,
        actor=manager,
        state=FeatureFlag.State.PILOT,
        reason="pilot acceptance approved",
        target_users=[str(pilot.pk)],
        acceptance_evidence="EVD-FLAG-1",
        rollback_plan="return to disabled",
    )
    assert evaluate_flag("new-dashboard", context=context).enabled
    denied = evaluate_flag(
        "new-dashboard",
        context=context,
        user=manager,
        required_action="analytics.view",
    )
    assert not denied.enabled and denied.reason == "permission-denied"
    disabled = transition_flag(
        enabled,
        actor=manager,
        state=FeatureFlag.State.DISABLED,
        reason="pilot rollback exercised",
    )
    assert disabled.version == 3
    assert not evaluate_flag("new-dashboard", context=context).enabled


@pytest.mark.django_db
def test_pr14_kill_switch_stops_job_but_normal_flag_snapshot_finishes():
    manager = assigned_user("kill-manager", "feature_flag.manage")
    context = FlagContext(environment=settings.OBE_ENV, user_id="worker")
    switch = create_flag(actor=manager, code="export", owner="platform", kill_switch=True)
    switch = transition_flag(
        switch,
        actor=manager,
        state=FeatureFlag.State.GENERAL,
        reason="export launch approved",
        target_users=["*"],
        acceptance_evidence="EVD-EXPORT-1",
        rollback_plan="disable export switch",
    )
    snapshot = flag_snapshot("export", context=context)
    assert snapshot["enabled"] and validate_flag_snapshot(snapshot)
    job, _ = create_job(
        task_name="exports.generate",
        queue="reports",
        idempotency_key="export:flag:1",
        payload={},
        feature_snapshot=snapshot,
    )
    transition_flag(
        switch,
        actor=manager,
        state=FeatureFlag.State.DISABLED,
        reason="kill switch incident drill",
    )
    assert (
        execute_job(job.id, generation=1, operation=lambda _progress: {}).status == "unauthorized"
    )

    normal = create_flag(actor=manager, code="guided-help", owner="learning")
    normal = transition_flag(
        normal,
        actor=manager,
        state=FeatureFlag.State.GENERAL,
        reason="general release approved",
        target_users=["*"],
        acceptance_evidence="EVD-HELP-1",
        rollback_plan="disable guided help",
    )
    normal_snapshot = flag_snapshot("guided-help", context=context)
    transition_flag(
        normal,
        actor=manager,
        state=FeatureFlag.State.DISABLED,
        reason="new sessions disabled",
    )
    assert validate_flag_snapshot(normal_snapshot)
    normal_job, _ = create_job(
        task_name="help.finish",
        queue="interactive",
        idempotency_key="help:flag:1",
        payload={},
        feature_snapshot=normal_snapshot,
    )
    assert (
        execute_job(normal_job.id, generation=1, operation=lambda _progress: {"ok": True}).status
        == "succeeded"
    )


def test_pr11_pr14_acceptance_contract_is_machine_readable():
    payload = json.loads((ROOT / "docs/security-controls.json").read_text(encoding="utf-8"))
    assert payload["finding_summary"] == {"critical": 0, "high": 0}
    assert {control["owner"] for control in payload["controls"]} == {
        "platform",
        "security",
        "prodi",
        "auditor",
    }
