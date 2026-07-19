from config.settings.base import *  # noqa: F403
from config.settings.runtime import validate_runtime_configuration

DEBUG = True
OBE_ENV = "local"
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

validate_runtime_configuration(globals(), "local")
