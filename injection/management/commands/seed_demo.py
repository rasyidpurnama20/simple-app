"""Management command to seed demo data (idempotent).

Usage: python manage.py seed_demo
"""

from django.core.management.base import BaseCommand

from injection.services import InjectionService


class Command(BaseCommand):
    help = "Seed demo data for the OBE System (idempotent)."

    def handle(self, *args, **options):
        log = InjectionService.seed_demo_data()
        self.stdout.write(
            self.style.SUCCESS(f"Demo data seeded successfully. Log: {log}")
        )
