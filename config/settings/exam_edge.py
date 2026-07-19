from django.core.exceptions import ImproperlyConfigured

from config.settings.production import *  # noqa: F403

OBE_AI_ENABLED = False
INSTALLED_APPS = [app for app in INSTALLED_APPS if app != "obe.ai"]  # noqa: F405
LITELLM_API_KEY = ""

if not OBE_EXAM_SIGNING_KEY:  # noqa: F405
    raise ImproperlyConfigured("OBE_EXAM_SIGNING_KEY_FILE wajib tersedia pada Exam Edge")
