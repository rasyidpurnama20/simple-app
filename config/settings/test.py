from config.settings.base import *  # noqa: F403
from config.settings.runtime import validate_runtime_configuration

DEBUG = False
OBE_ENV = "test"
CELERY_TASK_ALWAYS_EAGER = True
STORAGES = {"staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}}

validate_runtime_configuration(globals(), "test")
