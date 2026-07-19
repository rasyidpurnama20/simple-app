from config.settings.production import *  # noqa: F403
from config.settings.runtime import validate_runtime_configuration

OBE_ENV = "exam-edge"
OBE_AI_ENABLED = False
INSTALLED_APPS = [app for app in INSTALLED_APPS if app != "obe.ai"]  # noqa: F405
LITELLM_API_KEY = ""

validate_runtime_configuration(globals(), "exam-edge")
