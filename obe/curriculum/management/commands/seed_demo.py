from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Seed dataset sintetis OBE v5 dan akun demo secara idempotent"

    def handle(self, *args, **options):
        call_command("import_obe_sample", verbosity=options.get("verbosity", 1))
