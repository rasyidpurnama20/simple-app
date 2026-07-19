from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from obe.identity.services import authorize, require_permission
from obe.shared.models import FeatureFlag
from obe.shared.services import ActorContext, create_versioned, record_change

KILL_SWITCH_CODES = frozenset(
    {"ai", "heavy-analytics", "notification", "export", "integration-write", "secure-exam-sync"}
)


@dataclass(frozen=True)
class FlagContext:
    environment: str
    module: str = ""
    role: str = ""
    cohort: str = ""
    course: str = ""
    user_id: str = ""


@dataclass(frozen=True)
class FlagDecision:
    enabled: bool
    reason: str
    code: str
    version: int = 0
    state: str = "disabled"


def _cache_key(code: str, environment: str) -> str:
    return f"obe:feature-flag:{environment}:{code}:latest"


def _latest(code: str, environment: str) -> FeatureFlag | None:
    key = _cache_key(code, environment)
    cached_pk = cache.get(key)
    if cached_pk:
        cached = FeatureFlag.objects.filter(pk=cached_pk).first()
        if cached:
            return cached
    flag = FeatureFlag.objects.filter(code=code).order_by("-version").first()
    if flag:
        cache.set(key, flag.pk, timeout=30)
    return flag


def _scope_matches(flag: FeatureFlag, context: FlagContext) -> bool:
    scope = flag.scope
    checks = (
        not scope.get("environment") or context.environment in scope["environment"],
        not scope.get("module") or context.module == scope["module"],
        not scope.get("roles") or context.role in scope["roles"],
        not scope.get("cohorts") or context.cohort in scope["cohorts"],
        not scope.get("courses") or context.course in scope["courses"],
        not flag.target_users
        or "*" in {str(item) for item in flag.target_users}
        or context.user_id in {str(item) for item in flag.target_users},
    )
    return all(checks)


def evaluate_flag(
    code: str,
    *,
    context: FlagContext,
    user=None,
    required_action: str = "",
    permission_scope: dict[str, str] | None = None,
) -> FlagDecision:
    if required_action:
        decision = authorize(user, required_action, **(permission_scope or {}))
        if not decision.allowed:
            return FlagDecision(False, "permission-denied", code)
    flag = _latest(code, context.environment)
    if flag is None:
        return FlagDecision(False, "not-configured-default-disabled", code)
    if flag.state in {FeatureFlag.State.DISABLED, FeatureFlag.State.RETIRED}:
        return FlagDecision(False, flag.state, code, flag.version, flag.state)
    if flag.activation_date and flag.activation_date > timezone.now():
        return FlagDecision(False, "activation-pending", code, flag.version, flag.state)
    if not _scope_matches(flag, context):
        return FlagDecision(False, "outside-scope", code, flag.version, flag.state)
    if flag.state == FeatureFlag.State.INTERNAL and not getattr(user, "is_staff", False):
        return FlagDecision(False, "internal-only", code, flag.version, flag.state)
    return FlagDecision(True, "enabled", code, flag.version, flag.state)


@transaction.atomic
def create_flag(
    *,
    actor,
    code: str,
    owner: str,
    scope: dict[str, Any] | None = None,
    kill_switch: bool = False,
) -> FeatureFlag:
    require_permission(actor, "feature_flag.manage")
    if kill_switch and code not in KILL_SWITCH_CODES:
        raise ValidationError("Kode kill switch tidak terdaftar")
    if FeatureFlag.objects.filter(code=code).exists():
        raise ValidationError("Feature flag sudah ada")
    flag = create_versioned(
        FeatureFlag,
        actor_id=str(actor.pk),
        code=code,
        owner=owner,
        scope=scope or {"global": True},
        kill_switch=kill_switch,
    )
    record_change(
        actor=ActorContext(str(actor.pk), actor.get_username()),
        action="feature-flag.created",
        object_type="feature-flag",
        object_id=code,
        summary="Feature flag created disabled",
        reason="controlled feature introduction",
        after={"version": flag.version, "state": flag.state, "scope": flag.scope},
    )
    return flag


@transaction.atomic
def transition_flag(
    flag: FeatureFlag,
    *,
    actor,
    state: str,
    reason: str,
    target_users: list[str] | None = None,
    acceptance_evidence: str = "",
    rollback_plan: str = "",
    activation_date=None,
) -> FeatureFlag:
    require_permission(actor, "feature_flag.manage")
    if state not in FeatureFlag.State.values:
        raise ValidationError("State feature flag tidak valid")
    latest = (
        FeatureFlag.objects.select_for_update().filter(code=flag.code).order_by("-version").first()
    )
    if latest is None or latest.pk != flag.pk:
        raise ValidationError("Perubahan wajib memakai versi feature flag terbaru")
    next_flag = FeatureFlag(
        code=flag.code,
        version=flag.version + 1,
        state=state,
        scope=flag.scope,
        owner=flag.owner,
        activation_date=activation_date or timezone.now(),
        target_users=target_users if target_users is not None else flag.target_users,
        acceptance_evidence=acceptance_evidence or flag.acceptance_evidence,
        rollback_plan=rollback_plan or flag.rollback_plan,
        kill_switch=flag.kill_switch,
        created_by_actor_id=str(actor.pk),
        updated_by_actor_id=str(actor.pk),
    )
    next_flag.full_clean()
    next_flag.save()
    cache.delete_many(
        [
            _cache_key(flag.code, environment)
            for environment in ("local", "test", "staging", "production", "exam-edge", "*")
        ]
    )
    record_change(
        actor=ActorContext(str(actor.pk), actor.get_username()),
        action="feature-flag.transitioned",
        object_type="feature-flag",
        object_id=flag.code,
        summary=f"Feature flag transitioned to {state}",
        reason=reason,
        before={"version": flag.version, "state": flag.state},
        after={"version": next_flag.version, "state": next_flag.state},
    )
    return next_flag


def flag_snapshot(code: str, *, context: FlagContext, user=None, **permission) -> dict[str, Any]:
    snapshot = asdict(evaluate_flag(code, context=context, user=user, **permission))
    snapshot["context"] = asdict(context)
    return snapshot


def validate_flag_snapshot(snapshot: dict[str, Any], *, context: FlagContext | None = None) -> bool:
    if not snapshot.get("enabled"):
        return False
    context = context or FlagContext(**snapshot.get("context", {"environment": settings.OBE_ENV}))
    flag = _latest(str(snapshot["code"]), context.environment)
    if flag is None:
        return False
    if flag.kill_switch:
        return evaluate_flag(flag.code, context=context).enabled
    return int(snapshot.get("version", 0)) <= flag.version


def kill_switch_allows(code: str, *, context: FlagContext) -> bool:
    flag = _latest(code, context.environment)
    if flag is None:
        return True
    if not flag.kill_switch:
        return True
    return evaluate_flag(code, context=context).enabled


def require_feature(code: str, *, context: FlagContext, **options) -> FlagDecision:
    decision = evaluate_flag(code, context=context, **options)
    if not decision.enabled:
        raise PermissionDenied(f"Feature {code} tidak tersedia: {decision.reason}")
    return decision
