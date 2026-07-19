from django.core.exceptions import ImproperlyConfigured

from config.settings.base import *  # noqa: F403

if SECRET_KEY in {"", "unsafe-local-only", "local-only-change-me"}:  # noqa: F405
    raise ImproperlyConfigured("OBE_SECRET_KEY wajib diisi dengan secret produksi")
if not DATABASES["default"].get("PASSWORD"):  # noqa: F405
    raise ImproperlyConfigured("DATABASE_URL produksi wajib memakai password")

DEBUG = False
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
