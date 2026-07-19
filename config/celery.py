import os

from obe.shared.queueing import GuardedCelery, GuardedTask

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")
app = GuardedCelery("obe", task_cls=GuardedTask)
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
