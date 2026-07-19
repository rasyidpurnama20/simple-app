from config.settings.production import *  # noqa: F403
from config.settings.runtime import validate_runtime_configuration

OBE_ENV = "staging"
SECURE_HSTS_SECONDS = 3600
SECURE_HSTS_PRELOAD = False

validate_runtime_configuration(globals(), "staging")
