"""Management command to reset demo data.

Usage: python manage.py reset_demo
"""

from django.core.management.base import BaseCommand

from injection.services import InjectionService


class Command(BaseCommand):
    help = "Reset all demo data for the OBE System."

    def handle(self, *args, **options):
        log = InjectionService.reset_demo_data()
        self.stdout.write(
            self.style.SUCCESS(f"Demo data reset. Log: {log}")
        )
