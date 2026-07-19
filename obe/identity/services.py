import hashlib
import hmac
import os
import secrets
from dataclasses import asdict, dataclass
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from obe.identity.models import AccountSecurity, MFAChallenge, RoleAssignment
from obe.shared.services import ActorContext, record_change

DEMO_ACTIONS = {
    "prodi": [
        "curriculum.view",
        "curriculum.edit",
        "curriculum.clone",
        "curriculum.import",
        "curriculum.export",
        "curriculum.approve",
        "curriculum.activate",
        "allocation.approve",
        "rps.approve",
        "quality.view",
        "analytics.view",
        "user.manage",
        "rule.create",
        "rule.activate",
        "override.review",
        "appeal.review",
        "quality.release",
    ],
    "gpm": [
        "curriculum.view",
        "curriculum.review",
        "curriculum.validate",
        "curriculum.diff",
        "rps.review",
        "quality.edit",
        "analytics.view",
        "evidence.verify",
        "evidence.download",
        "rule.review",
        "quality.validate",
        "quality.verify",
        "appeal.review",
    ],
    "pengampu": [
        "rps.edit",
        "assessment.edit",
        "score.edit",
        "course.view",
        "analytics.view",
        "evidence.download",
        "decision.view",
        "override.request",
        "quality.resolve",
    ],
    "mahasiswa": [
        "course.view",
        "submission.edit",
        "portfolio.view",
        "task.view",
        "evidence.download",
        "decision.view",
        "appeal.submit",
    ],
}


def ensure_demo_assignments() -> dict:
    if not settings.DEBUG and settings.OBE_ENV != "test":
        raise RuntimeError("Seed demo hanya boleh dijalankan pada environment local/test")
    password = os.environ.get("OBE_DEMO_PASSWORD", "")
    if len(password) < 16:
        raise RuntimeError("OBE_DEMO_PASSWORD lokal wajib berisi minimal 16 karakter")
    User = get_user_model()
    system, _ = User.objects.get_or_create(username="system", defaults={"is_staff": True})
    users = {}
    for role in ("prodi", "gpm", "pengampu", "mahasiswa"):
        user, created = User.objects.get_or_create(username=role)
        if created or not user.has_usable_password():
            user.set_password(password)
            user.save(update_fields=["password"])
        users[role] = user
        RoleAssignment.objects.get_or_create(
            user=user,
            role=role,
            scope_type="global",
            scope_id="*",
            period="demo",
            defaults={"actions": DEMO_ACTIONS[role], "granted_by": system},
        )
    return users


@dataclass(frozen=True)
class PermissionDecision:
    allowed: bool
    reason: str
    assignment_id: int | None = None
    role: str = ""


def _scope_matches(
    assignment: RoleAssignment,
    *,
    scope_type: str,
    scope_id: str,
    period: str,
) -> bool:
    scope_match = assignment.scope_type == "global" or (
        assignment.scope_type == scope_type and assignment.scope_id in {"*", str(scope_id)}
    )
    period_match = not period or not assignment.period or assignment.period == period
    return scope_match and period_match


def authorize(
    user,
    action: str,
    *,
    scope_type: str = "global",
    scope_id: str = "*",
    period: str = "",
    owner_id: str = "",
) -> PermissionDecision:
    if isinstance(user, AnonymousUser) or not user.is_authenticated:
        return PermissionDecision(False, "unauthenticated")
    if user.is_superuser:
        return PermissionDecision(True, "superuser")
    now = timezone.now()
    assignments = RoleAssignment.objects.filter(
        user=user,
        starts_at__lte=now,
        revoked_at__isnull=True,
    ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
    for assignment in assignments:
        if assignment.role == RoleAssignment.Role.STUDENT:
            own_ids = {str(user.pk), user.get_username()}
            if owner_id and str(owner_id) not in own_ids:
                continue
            if scope_type == "student" and str(scope_id) not in own_ids:
                continue
        if _scope_matches(
            assignment,
            scope_type=scope_type,
            scope_id=str(scope_id),
            period=period,
        ) and ("*" in assignment.actions or action in assignment.actions):
            return PermissionDecision(True, "assignment", assignment.pk, assignment.role)
    return PermissionDecision(False, "no-active-assignment")


def can(
    user,
    action: str,
    *,
    scope_type: str = "global",
    scope_id: str = "*",
    period: str = "",
    owner_id: str = "",
) -> bool:
    return authorize(
        user,
        action,
        scope_type=scope_type,
        scope_id=scope_id,
        period=period,
        owner_id=owner_id,
    ).allowed


def require_permission(user, action: str, **scope: str) -> PermissionDecision:
    decision = authorize(user, action, **scope)
    if not decision.allowed:
        raise PermissionDenied("Akses ditolak oleh scoped permission service")
    return decision


def permission_snapshot(user, action: str, **scope: str) -> dict[str, Any]:
    decision = require_permission(user, action, **scope)
    profile, _ = AccountSecurity.objects.get_or_create(user=user)
    return {
        "user_id": str(user.pk),
        "action": action,
        "scope": scope,
        "assignment_id": decision.assignment_id,
        "permission_epoch": profile.permission_epoch,
    }


def validate_permission_snapshot(snapshot: dict[str, Any]) -> bool:
    if not snapshot:
        return True
    User = get_user_model()
    try:
        user = User.objects.get(pk=snapshot["user_id"], is_active=True)
        profile = AccountSecurity.objects.get(user=user)
    except (User.DoesNotExist, AccountSecurity.DoesNotExist, KeyError):
        return False
    if profile.permission_epoch != snapshot.get("permission_epoch"):
        return False
    scope = snapshot.get("scope", {})
    return can(user, snapshot.get("action", ""), **scope)


def account_security(user) -> AccountSecurity:
    profile, _ = AccountSecurity.objects.get_or_create(user=user)
    return profile


@transaction.atomic
def register_login_failure(user, *, ip_address: str | None = None) -> AccountSecurity:
    profile, _ = AccountSecurity.objects.select_for_update().get_or_create(user=user)
    profile.failed_attempts += 1
    threshold = int(getattr(settings, "OBE_LOGIN_LOCK_THRESHOLD", 5))
    if profile.failed_attempts >= threshold:
        profile.locked_until = timezone.now() + timedelta(
            seconds=int(getattr(settings, "OBE_LOGIN_LOCK_SECONDS", 900))
        )
        profile.failed_attempts = 0
    if ip_address:
        profile.last_login_ip = ip_address
    profile.save(update_fields=["failed_attempts", "locked_until", "last_login_ip", "updated_at"])
    return profile


@transaction.atomic
def register_login_success(user, *, ip_address: str | None = None) -> AccountSecurity:
    profile, _ = AccountSecurity.objects.select_for_update().get_or_create(user=user)
    if profile.locked:
        raise PermissionDenied("Akun dikunci sementara")
    profile.failed_attempts = 0
    profile.locked_until = None
    profile.last_login_ip = ip_address or profile.last_login_ip
    profile.save(update_fields=["failed_attempts", "locked_until", "last_login_ip", "updated_at"])
    return profile


@transaction.atomic
def grant_assignment(
    *,
    granter,
    user,
    role: str,
    scope_type: str,
    scope_id: str,
    actions: list[str],
    period: str = "",
    expires_at=None,
) -> RoleAssignment:
    require_permission(
        granter,
        "assignment.manage",
        scope_type=scope_type,
        scope_id=scope_id,
        period=period,
    )
    assignment = RoleAssignment(
        user=user,
        role=role,
        scope_type=scope_type,
        scope_id=str(scope_id),
        actions=sorted(set(actions)),
        period=period,
        expires_at=expires_at,
        granted_by=granter,
    )
    assignment.full_clean()
    assignment.save()
    AccountSecurity.objects.get_or_create(user=user)
    AccountSecurity.objects.filter(user=user).update(permission_epoch=F("permission_epoch") + 1)
    record_change(
        actor=ActorContext(str(granter.pk), granter.get_username(), f"{scope_type}:{scope_id}"),
        actor_role="prodi",
        assignment_reference=str(assignment.pk),
        action="identity.assignment.granted",
        object_type="role-assignment",
        object_id=str(assignment.pk),
        summary="Scoped role assignment granted",
        after={"role": role, "scope_type": scope_type, "scope_id": str(scope_id), "period": period},
        reason="authorized assignment management",
    )
    return assignment


@transaction.atomic
def revoke_assignment(*, assignment: RoleAssignment, actor, reason: str) -> None:
    if not reason.strip():
        raise ValidationError("Alasan pencabutan assignment wajib diisi")
    require_permission(
        actor,
        "assignment.manage",
        scope_type=assignment.scope_type,
        scope_id=assignment.scope_id,
        period=assignment.period,
    )
    locked = RoleAssignment.objects.select_for_update().get(pk=assignment.pk)
    locked.revoked_at = timezone.now()
    locked.save(update_fields=["revoked_at", "updated_at"])
    AccountSecurity.objects.filter(user=locked.user).update(
        permission_epoch=F("permission_epoch") + 1
    )
    record_change(
        actor=ActorContext(
            str(actor.pk), actor.get_username(), f"{locked.scope_type}:{locked.scope_id}"
        ),
        actor_role="prodi",
        assignment_reference=str(locked.pk),
        action="identity.assignment.revoked",
        object_type="role-assignment",
        object_id=str(locked.pk),
        summary="Scoped role assignment revoked",
        reason=reason.strip(),
    )


def issue_mfa_challenge(user, *, ttl_seconds: int = 300) -> tuple[MFAChallenge, str]:
    profile = account_security(user)
    if not profile.mfa_enabled:
        raise ValidationError("MFA belum diaktifkan untuk akun")
    raw = secrets.token_urlsafe(32)
    challenge = MFAChallenge.objects.create(
        user=user,
        token_hash=hashlib.sha256(raw.encode()).hexdigest(),
        expires_at=timezone.now() + timedelta(seconds=ttl_seconds),
    )
    return challenge, raw


@transaction.atomic
def verify_mfa_challenge(challenge_id: int, token: str, *, user) -> bool:
    challenge = MFAChallenge.objects.select_for_update().get(pk=challenge_id, user=user)
    if not challenge.usable:
        return False
    challenge.attempts += 1
    valid = hmac.compare_digest(challenge.token_hash, hashlib.sha256(token.encode()).hexdigest())
    if valid:
        challenge.consumed_at = timezone.now()
    challenge.save(update_fields=["attempts", "consumed_at", "updated_at"])
    return valid


@transaction.atomic
def provision_user(*, actor, username: str, email: str, scope_id: str, password: str | None = None):
    require_permission(actor, "user.manage", scope_type="program", scope_id=scope_id)
    User = get_user_model()
    user = User(username=username.strip(), email=User.objects.normalize_email(email))
    if password:
        validate_password(password, user=user)
        user.set_password(password)
    else:
        user.set_unusable_password()
    user.full_clean()
    user.save()
    AccountSecurity.objects.create(user=user, password_reset_required=not bool(password))
    record_change(
        actor=ActorContext(str(actor.pk), actor.get_username(), f"program:{scope_id}"),
        actor_role="prodi",
        action="identity.user.created",
        object_type="user",
        object_id=str(user.pk),
        summary="User provisioned by Prodi",
        after={"username": user.get_username(), "active": user.is_active},
        reason="program user administration",
    )
    return user


def decision_dict(decision: PermissionDecision) -> dict[str, Any]:
    return asdict(decision)
