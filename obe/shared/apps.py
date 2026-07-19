from django.apps import AppConfig


class SharedConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "obe.shared"

    def ready(self):
        from obe.shared.queueing import install_celery_guards
        from obe.shared.telemetry import configure_telemetry

        install_celery_guards()
        configure_telemetry()
