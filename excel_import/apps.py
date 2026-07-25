"""Django app config for excel_import."""

from django.apps import AppConfig


class ExcelImportConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "excel_import"
    verbose_name = "Excel Import"
