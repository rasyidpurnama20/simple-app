import os

from config.settings.base import *  # noqa: F403
from config.settings.runtime import validate_runtime_configuration

DEBUG = False
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
EVIDENCE_ANTIVIRUS_REQUIRED = True

if os.environ.get("DJANGO_SETTINGS_MODULE", "").endswith(".production"):
    validate_runtime_configuration(globals(), "production")
