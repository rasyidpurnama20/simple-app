from __future__ import annotations

from functools import wraps

from django.core.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import BasePermission

from obe.identity.services import can, require_permission


def require_action(action: str, *, scope_type: str = "global", scope_kwarg: str = ""):
    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            scope_id = str(kwargs.get(scope_kwarg, "*")) if scope_kwarg else "*"
            require_permission(
                request.user,
                action,
                scope_type=scope_type,
                scope_id=scope_id,
            )
            return view(request, *args, **kwargs)

        return wrapped

    return decorator


class ScopedActionPermission(BasePermission):
    action = ""
    scope_type = "global"
    scope_kwarg = ""

    def has_permission(self, request, view):
        action = getattr(view, "required_action", self.action)
        scope_type = getattr(view, "scope_type", self.scope_type)
        scope_kwarg = getattr(view, "scope_kwarg", self.scope_kwarg)
        scope_id = str(view.kwargs.get(scope_kwarg, "*")) if scope_kwarg else "*"
        return bool(action) and can(
            request.user,
            action,
            scope_type=scope_type,
            scope_id=scope_id,
        )


def require_distinct_approver(*, maker_id: str, approver_id: str) -> None:
    if str(maker_id) == str(approver_id):
        raise ValidationError("Self-approval tidak diizinkan")


def deny_direct_object_access() -> None:
    raise PermissionDenied("Akses object wajib melalui scoped permission service")
