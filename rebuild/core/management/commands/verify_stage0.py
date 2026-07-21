from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from core.roles import ROLES


class Command(BaseCommand):
    help = "Verifikasi akun dan batas peran minimum Tahap 0"

    def handle(self, *args, **options):
        user_model = get_user_model()
        problems = []
        for role in ROLES:
            user = user_model.objects.filter(username=role.code).first()
            if user is None:
                problems.append(f"akun {role.code} tidak ditemukan")
            elif set(user.groups.values_list("name", flat=True)) != {role.code}:
                problems.append(f"kelompok akun {role.code} tidak tepat")

        if problems:
            raise CommandError("; ".join(problems))
        self.stdout.write(
            self.style.SUCCESS("Verifikasi Tahap 0 lulus: empat akun dan peran siap.")
        )
