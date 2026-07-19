from config.settings.base import *  # noqa: F403

DEBUG = False
OBE_ENV = "test"
CELERY_TASK_ALWAYS_EAGER = True
STORAGES = {"staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}}
