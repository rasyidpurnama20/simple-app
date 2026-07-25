"""WSGI config for the OBE_System project."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "obe_system.settings")

application = get_wsgi_application()
