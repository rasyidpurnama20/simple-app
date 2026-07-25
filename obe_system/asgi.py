"""ASGI config for the OBE_System project."""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "obe_system.settings")

application = get_asgi_application()
