import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.db.models import Q
from django.utils import timezone

from obe.identity.models import RoleAssignment

DEMO_ACTIONS = {
    "prodi": [
        "curriculum.view",
        "curriculum.edit",
        "rps.approve",
        "quality.view",
        "analytics.view",
        "user.manage",
    ],
    "gpm": ["curriculum.view", "rps.review", "quality.edit", "analytics.view", "evidence.verify"],
    "pengampu": ["rps.edit", "assessment.edit", "score.edit", "course.view", "analytics.view"],
    "mahasiswa": ["course.view", "submission.edit", "portfolio.view", "task.view"],
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


def can(user, action: str, *, scope_type: str = "global", scope_id: str = "*") -> bool:
    if isinstance(user, AnonymousUser) or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    now = timezone.now()
    assignments = RoleAssignment.objects.filter(
        user=user,
        starts_at__lte=now,
        revoked_at__isnull=True,
    ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
    for assignment in assignments:
        scope_match = assignment.scope_type == "global" or (
            assignment.scope_type == scope_type and assignment.scope_id in {"*", str(scope_id)}
        )
        if scope_match and ("*" in assignment.actions or action in assignment.actions):
            return True
    return False
