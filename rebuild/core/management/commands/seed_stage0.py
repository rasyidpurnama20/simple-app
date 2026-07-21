import os

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.roles import ROLES


class Command(BaseCommand):
    help = "Buat atau sinkronkan empat akun demo Tahap 0 secara idempotent"

    @transaction.atomic
    def handle(self, *args, **options):
        password = os.environ.get("STAGE0_DEMO_PASSWORD", "belajar-tahap0")
        if len(password) < 8:
            raise CommandError("STAGE0_DEMO_PASSWORD minimal 8 karakter")

        user_model = get_user_model()
        for role in ROLES:
            group, _ = Group.objects.get_or_create(name=role.code)
            user, _ = user_model.objects.get_or_create(
                username=role.code,
                defaults={"email": f"{role.code}@example.invalid"},
            )
            user.email = f"{role.code}@example.invalid"
            user.is_active = True
            user.is_staff = False
            user.is_superuser = False
            user.set_password(password)
            user.save()
            user.groups.set([group])

        self.stdout.write(self.style.SUCCESS("Empat akun demo Tahap 0 siap."))
