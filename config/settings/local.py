from config.settings.base import *  # noqa: F403
from config.settings.base import env
from config.settings.runtime import validate_runtime_configuration

DEBUG = True
OBE_ENV = "local"
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# The quickstart exposes Nginx on a configurable host port. Trust only the two
# loopback origins for that selected port unless an explicit allowlist is set.
_LOCAL_HTTP_PORT = env("OBE_HTTP_PORT", default="8000")
CSRF_TRUSTED_ORIGINS = env.list(
    "OBE_CSRF_TRUSTED_ORIGINS",
    default=[
        f"http://localhost:{_LOCAL_HTTP_PORT}",
        f"http://127.0.0.1:{_LOCAL_HTTP_PORT}",
    ],
)

validate_runtime_configuration(globals(), "local")
