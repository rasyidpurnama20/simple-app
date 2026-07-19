import logging
import re
from collections.abc import Iterable, Mapping
from typing import Any

from django.views.debug import SafeExceptionReporterFilter

REDACTED = "[REDACTED]"
SENSITIVE_KEY = re.compile(
    r"(?i)(password|passwd|secret|token|api[-_]?key|authorization|cookie|session|"
    r"signing[-_]?key|database[-_]?url|exam[-_]?answer|private[-_]?key)"
)
KEY_VALUE = re.compile(
    r"(?i)(password|passwd|secret|token|api[-_]?key|authorization|cookie|session|"
    r"signing[-_]?key|database[-_]?url)(\s*[=:]\s*)(['\"]?)([^\s,;}\"']+)(['\"]?)"
)
URL_CREDENTIAL = re.compile(r"(?P<scheme>[a-z][a-z0-9+.-]*://[^:/\s]+:)(?P<secret>[^@/\s]+)@")
BEARER = re.compile(r"(?i)(bearer\s+)[a-z0-9._~+/=-]+")
_registered_values: set[str] = set()


def register_sensitive_values(values: Iterable[str]) -> None:
    _registered_values.update(value for value in values if value and len(value) >= 4)


def redact_text(value: str) -> str:
    redacted = value
    for secret in sorted(_registered_values, key=len, reverse=True):
        redacted = redacted.replace(secret, REDACTED)
    redacted = URL_CREDENTIAL.sub(r"\g<scheme>[REDACTED]@", redacted)
    redacted = BEARER.sub(r"\1[REDACTED]", redacted)
    return KEY_VALUE.sub(r"\1\2\3[REDACTED]\5", redacted)


def redact(value: Any, *, key: str = "") -> Any:
    if key and SENSITIVE_KEY.search(key):
        return REDACTED
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, Mapping):
        return {item_key: redact(item, key=str(item_key)) for item_key, item in value.items()}
    if isinstance(value, tuple):
        return tuple(redact(item) for item in value)
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


class SecretRedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_text(record.getMessage())
        record.args = ()
        for key, value in vars(record).items():
            if SENSITIVE_KEY.search(key):
                setattr(record, key, REDACTED)
            elif isinstance(value, str | dict | list | tuple):
                setattr(record, key, redact(value, key=key))
        return True


class RedactingFormatter(logging.Formatter):
    def formatException(self, exc_info) -> str:
        return redact_text(super().formatException(exc_info))


class OBEExceptionReporterFilter(SafeExceptionReporterFilter):
    def get_safe_request_meta(self, request):
        return redact(super().get_safe_request_meta(request))

    def get_safe_cookies(self, request):
        return redact(super().get_safe_cookies(request))

    def get_safe_settings(self):
        return redact(super().get_safe_settings())

    def get_post_parameters(self, request):
        return redact(super().get_post_parameters(request))
