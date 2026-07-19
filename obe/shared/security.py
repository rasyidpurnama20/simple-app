from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from django.conf import settings
from django.utils.http import url_has_allowed_host_and_scheme

from obe.identity.models import RoleAssignment
from obe.shared.ephemeral import allow_rate


@dataclass(frozen=True)
class RatePolicy:
    name: str
    prefix: str
    anonymous_limit: int
    authenticated_limit: int
    window_seconds: int
    role_limits: dict[str, int] = field(default_factory=dict)


RATE_POLICIES = (
    RatePolicy("login", "/accounts/login/", 5, 10, 300),
    RatePolicy("credential-reset", "/accounts/password-reset/", 3, 5, 900),
    RatePolicy("file", "/evidence/", 5, 30, 60, {"gpm": 60, "prodi": 60}),
    RatePolicy("export", "/api/v1/export/", 1, 5, 60, {"gpm": 10, "prodi": 10}),
    RatePolicy("ai", "/api/v1/ai/", 1, 20, 60, {"pengampu": 30}),
    RatePolicy("expensive", "/api/v1/analytics/", 2, 20, 60, {"gpm": 60}),
    RatePolicy("api", "/api/", 10, 120, 60, {"gpm": 180, "prodi": 180}),
)


def policy_for_path(path: str) -> RatePolicy | None:
    return next((policy for policy in RATE_POLICIES if path.startswith(policy.prefix)), None)


def _active_role(user) -> str:
    if not getattr(user, "is_authenticated", False):
        return "anonymous"
    assignment = (
        RoleAssignment.objects.filter(user=user, revoked_at__isnull=True).order_by("role").first()
    )
    return assignment.role if assignment and assignment.active else "authenticated"


def enforce_rate(request, policy: RatePolicy) -> tuple[bool, int]:
    authenticated = getattr(request.user, "is_authenticated", False)
    role = _active_role(request.user)
    limit = (
        policy.role_limits.get(role, policy.authenticated_limit)
        if authenticated
        else policy.anonymous_limit
    )
    identity = str(request.user.pk) if authenticated else request.META.get("REMOTE_ADDR", "unknown")
    allowed = allow_rate(
        f"http:{policy.name}:{role}",
        identity,
        limit=limit,
        window_seconds=policy.window_seconds,
    )
    return allowed, limit


def safe_redirect_target(target: str, *, allowed_hosts: set[str], require_https: bool) -> str:
    if not target or not url_has_allowed_host_and_scheme(
        target,
        allowed_hosts=allowed_hosts,
        require_https=require_https,
    ):
        return "/"
    return target


def validate_outbound_url(url: str, *, allowed_hosts: set[str] | None = None) -> str:
    parsed = urlsplit(url)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username:
        raise ValueError("URL outbound tidak aman")
    hosts = allowed_hosts
    if hosts is None:
        hosts = set(getattr(settings, "OBE_OUTBOUND_ALLOWED_HOSTS", []))
    if parsed.hostname not in hosts:
        raise ValueError("Host outbound tidak ada dalam allowlist")
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(parsed.hostname, parsed.port or 443)}
    except socket.gaierror as exc:
        raise ValueError("Host outbound tidak dapat di-resolve") from exc
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if not ip.is_global:
            raise ValueError("Alamat private/reserved tidak boleh menjadi tujuan outbound")
    return parsed.geturl()


def isolated_upload_name(filename: str, *, allowed_extensions: set[str]) -> str:
    name = Path(filename.replace("\\", "/")).name
    suffix = Path(name).suffix.lower()
    if not name or suffix not in allowed_extensions or "\x00" in name:
        raise ValueError("Nama atau ekstensi upload tidak diizinkan")
    return name[:255]
