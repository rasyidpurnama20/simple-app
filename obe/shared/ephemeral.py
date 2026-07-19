from __future__ import annotations

import hashlib
import secrets
from contextlib import contextmanager
from typing import Any

from django.core.cache import caches

MAX_EPHEMERAL_TTL = 24 * 60 * 60


def _key(namespace: str, subject: str) -> str:
    digest = hashlib.sha256(subject.encode()).hexdigest()
    return f"obe:ephemeral:{namespace}:{digest}"


def put_short_state(namespace: str, subject: str, value: Any, *, ttl: int) -> None:
    if not 1 <= ttl <= MAX_EPHEMERAL_TTL:
        raise ValueError("TTL short-lived state harus 1–86400 detik")
    caches["default"].set(_key(namespace, subject), value, timeout=ttl)


def get_short_state(namespace: str, subject: str, default: Any = None) -> Any:
    return caches["default"].get(_key(namespace, subject), default)


def allow_rate(namespace: str, subject: str, *, limit: int, window_seconds: int) -> bool:
    if limit < 1 or not 1 <= window_seconds <= 3_600:
        raise ValueError("Kebijakan rate limit tidak valid")
    backend = caches["default"]
    key = _key(f"rate:{namespace}", subject)
    if backend.add(key, 1, timeout=window_seconds):
        return True
    try:
        current = backend.incr(key)
    except ValueError:
        backend.set(key, 1, timeout=window_seconds)
        current = 1
    return current <= limit


@contextmanager
def ephemeral_lock(namespace: str, subject: str, *, ttl: int = 30):
    if not 1 <= ttl <= 300:
        raise ValueError("TTL lock harus 1–300 detik")
    backend = caches["default"]
    name = _key(f"lock:{namespace}", subject)
    if hasattr(backend, "lock"):
        lock = backend.lock(name, timeout=ttl, blocking_timeout=0)
        acquired = lock.acquire(blocking=False)
        try:
            yield acquired
        finally:
            if acquired:
                lock.release()
        return
    token = secrets.token_urlsafe(16)
    acquired = backend.add(name, token, timeout=ttl)
    try:
        yield acquired
    finally:
        if acquired and backend.get(name) == token:
            backend.delete(name)
