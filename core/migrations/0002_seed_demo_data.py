"""Seed a demo Program of Study and demo users (Kaprodi, Lecturer).

This is a DATA migration (Requirement 18.1: schema and seed applied through
migrations, not ad-hoc scripts). It is idempotent - re-running leaves the same
data - so it is safe alongside repeated `docker compose up` startups.
The Role_Switcher (Requirement 15.1/15.2) needs these rows to offer options.
"""

from django.db import migrations


def seed_demo_data(apps, schema_editor):
    ProgramOfStudy = apps.get_model("core", "ProgramOfStudy")
    DemoUser = apps.get_model("core", "DemoUser")

    prodi, _ = ProgramOfStudy.objects.get_or_create(
        code="IF",
        defaults={
            "name": "Teknik Informatika",
            "faculty": "Fakultas Teknik",
        },
    )

    # Keyed on (name, role) so re-runs upsert rather than duplicate.
    DemoUser.objects.get_or_create(
        name="Dr. Sari (Kaprodi)",
        role="kaprodi",
        defaults={"prodi": prodi},
    )
    DemoUser.objects.get_or_create(
        name="Budi, M.Kom (Dosen)",
        role="lecturer",
        defaults={"prodi": prodi},
    )


def unseed_demo_data(apps, schema_editor):
    DemoUser = apps.get_model("core", "DemoUser")
    ProgramOfStudy = apps.get_model("core", "ProgramOfStudy")
    DemoUser.objects.filter(
        name__in=["Dr. Sari (Kaprodi)", "Budi, M.Kom (Dosen)"]
    ).delete()
    ProgramOfStudy.objects.filter(code="IF").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_demo_data, unseed_demo_data),
    ]
