"""Seed a demo Timeline_Template and one instantiated OBE cycle.

This is a DATA migration (Requirement 18.1: seeds applied through migrations,
not ad-hoc scripts). It is idempotent - keyed ``get_or_create`` calls mean a
re-run leaves the same data - so it is safe across repeated
``docker compose up`` startups.

It creates:
  * a reusable Timeline_Template with three phases, milestones, tasks,
    checklist items, and hard/soft dependency edges, and
  * one instantiated TimelineInstance bound to a demo OBECycle whose tasks are
    assigned to the demo Kaprodi with varied statuses, so the Home workspace
    shows real "Do Now / Next / Waiting on Others" data after startup.
"""

from datetime import date, timedelta

from django.db import migrations

TEMPLATE_NAME = "Template Siklus OBE Standar"
CYCLE_NAME = "Siklus OBE 2025/2026 (Demo)"


def _get_demo_users(DemoUser):
    kaprodi = DemoUser.objects.filter(role="kaprodi").first()
    lecturer = DemoUser.objects.filter(role="lecturer").first()
    return kaprodi, lecturer


def seed_demo_timeline(apps, schema_editor):
    ProgramOfStudy = apps.get_model("core", "ProgramOfStudy")
    DemoUser = apps.get_model("core", "DemoUser")
    TimelineTemplate = apps.get_model("timeline", "TimelineTemplate")
    TimelineInstance = apps.get_model("timeline", "TimelineInstance")
    OBECycle = apps.get_model("timeline", "OBECycle")
    Phase = apps.get_model("timeline", "Phase")
    Milestone = apps.get_model("timeline", "Milestone")
    Task = apps.get_model("timeline", "Task")
    ChecklistItem = apps.get_model("timeline", "ChecklistItem")
    TaskDependency = apps.get_model("timeline", "TaskDependency")

    prodi = ProgramOfStudy.objects.filter(code="IF").first()
    kaprodi, lecturer = _get_demo_users(DemoUser)
    if prodi is None or kaprodi is None:
        # Core seed has not run; nothing to attach the demo timeline to.
        return

    base = date(2025, 9, 1)

    # ---------------------------------------------------------------
    # 1. Template structure (idempotent on the unique template name).
    # ---------------------------------------------------------------
    template, created = TimelineTemplate.objects.get_or_create(
        name=TEMPLATE_NAME,
        defaults={"description": "Template standar tiga fase: Persiapan, Pelaksanaan, Evaluasi."},
    )
    if created:
        p1 = Phase.objects.create(template=template, name="Persiapan", order=0)
        p2 = Phase.objects.create(template=template, name="Pelaksanaan", order=1)
        p3 = Phase.objects.create(template=template, name="Evaluasi", order=2)

        m1 = Milestone.objects.create(
            phase=p1, name="Kurikulum & RPS Siap", milestone_date=base + timedelta(days=30), order=0
        )
        m2 = Milestone.objects.create(
            phase=p2, name="Perkuliahan Berjalan", milestone_date=base + timedelta(days=90), order=0
        )
        m3 = Milestone.objects.create(
            phase=p3, name="Evaluasi Ketercapaian", milestone_date=base + timedelta(days=120), order=0
        )

        t_review = Task.objects.create(
            milestone=m1, title="Tinjau kurikulum aktif", order=0,
            deadline_kind="fixed", fixed_date=base + timedelta(days=10),
            explanation_what="Meninjau kurikulum aktif program studi.",
            explanation_why="Memastikan RPS mengacu pada CPL yang berlaku.",
            explanation_who="Kaprodi",
            explanation_when="Sepuluh hari setelah siklus dimulai.",
            explanation_how="Buka kurikulum aktif dan periksa daftar CPL.",
            explanation_next="Setelah selesai, penyusunan RPS dapat dimulai.",
        )
        t_rps = Task.objects.create(
            milestone=m1, title="Susun RPS mata kuliah", order=1,
            deadline_kind="relative", relative_offset_days=-5,
            relative_reference_milestone=m1,
            explanation_what="Menyusun RPS untuk setiap mata kuliah.",
            explanation_why="RPS menjadi dasar penilaian berbasis rubrik.",
            explanation_who="Dosen Pengampu",
            explanation_when="Lima hari sebelum milestone kurikulum siap.",
            explanation_how="Gunakan wizard penyusunan RPS pada ruang kerja Learning.",
            explanation_next="Setelah RPS diajukan, penilaian dapat dilakukan.",
        )
        t_grade = Task.objects.create(
            milestone=m2, title="Nilai rubrik mahasiswa", order=0,
            deadline_kind="relative", relative_offset_days=0,
            relative_reference_milestone=m2,
            explanation_what="Menilai pekerjaan mahasiswa memakai rubrik.",
            explanation_why="Skor rubrik menjadi bukti ketercapaian.",
            explanation_who="Dosen Pengampu",
            explanation_when="Pada milestone perkuliahan berjalan.",
            explanation_how="Masukkan skor untuk setiap kriteria rubrik.",
            explanation_next="Skor digunakan untuk perhitungan ketercapaian.",
        )
        t_calc = Task.objects.create(
            milestone=m3, title="Hitung ketercapaian CPL", order=0,
            deadline_kind="relative", relative_offset_days=0,
            relative_reference_milestone=m3,
            explanation_what="Menghitung ketercapaian CPL dari skor rubrik.",
            explanation_why="Menemukan capaian yang belum memenuhi target.",
            explanation_who="Kaprodi",
            explanation_when="Pada milestone evaluasi ketercapaian.",
            explanation_how="Jalankan perhitungan pada ruang kerja Attainment.",
            explanation_next="Gap memicu tugas evaluasi tindak lanjut.",
        )

        ChecklistItem.objects.create(task=t_review, text="Periksa daftar CPL", order=0)
        ChecklistItem.objects.create(task=t_review, text="Catat perubahan", order=1)
        ChecklistItem.objects.create(task=t_rps, text="Isi CPMK & Sub-CPMK", order=0)
        ChecklistItem.objects.create(task=t_rps, text="Definisikan rubrik", order=1)

        # Dependency edges: RPS hard-depends on review; grading soft-depends on
        # RPS; calculation hard-depends on grading.
        TaskDependency.objects.create(predecessor=t_review, successor=t_rps, kind="hard")
        TaskDependency.objects.create(predecessor=t_rps, successor=t_grade, kind="soft")
        TaskDependency.objects.create(predecessor=t_grade, successor=t_calc, kind="hard")

    # ---------------------------------------------------------------
    # 2. One instantiated cycle with tasks for the Home workspace.
    # ---------------------------------------------------------------
    if not OBECycle.objects.filter(name=CYCLE_NAME).exists():
        cycle = OBECycle.objects.create(
            name=CYCLE_NAME, academic_year="2025/2026", start_date=base,
            prodi=prodi, owner=kaprodi, creator=kaprodi, status="active", version=1,
        )
        instance = TimelineInstance.objects.create(template=template, cycle=cycle)

        ip1 = Phase.objects.create(instance=instance, name="Persiapan", order=0)
        ip2 = Phase.objects.create(instance=instance, name="Pelaksanaan", order=1)
        ip3 = Phase.objects.create(instance=instance, name="Evaluasi", order=2)

        im1 = Milestone.objects.create(
            phase=ip1, name="Kurikulum & RPS Siap", milestone_date=base + timedelta(days=30), order=0
        )
        im2 = Milestone.objects.create(
            phase=ip2, name="Perkuliahan Berjalan", milestone_date=base + timedelta(days=90), order=0
        )
        im3 = Milestone.objects.create(
            phase=ip3, name="Evaluasi Ketercapaian", milestone_date=base + timedelta(days=120), order=0
        )

        far = date.today() + timedelta(days=180)

        # Do Now (Siap Dikerjakan), owned by the demo Kaprodi.
        Task.objects.create(
            milestone=im1, title="Tinjau kurikulum aktif", order=0, owner=kaprodi,
            status="siap_dikerjakan", deadline_kind="fixed", fixed_date=far,
            resolved_deadline=far,
            explanation_what="Meninjau kurikulum aktif program studi.",
            explanation_why="Memastikan RPS mengacu pada CPL yang berlaku.",
            explanation_who="Kaprodi",
            explanation_when=f"Jatuh tempo {far:%d %b %Y}.",
            explanation_how="Buka kurikulum aktif dan periksa daftar CPL.",
            explanation_next="Setelah selesai, penyusunan RPS menjadi siap.",
        )
        # Do Now (Dikerjakan), owned by the demo Kaprodi.
        Task.objects.create(
            milestone=im1, title="Finalisasi jadwal siklus", order=1, owner=kaprodi,
            status="dikerjakan", deadline_kind="fixed", fixed_date=far,
            resolved_deadline=far,
            explanation_what="Menetapkan jadwal seluruh fase siklus.",
            explanation_why="Jadwal yang jelas menjaga siklus tepat waktu.",
            explanation_who="Kaprodi",
            explanation_when=f"Jatuh tempo {far:%d %b %Y}.",
            explanation_how="Tetapkan tanggal untuk setiap milestone.",
            explanation_next="Jadwal menjadi acuan tenggat tugas.",
        )
        # Next (Belum Siap), owned by the demo Kaprodi.
        Task.objects.create(
            milestone=im2, title="Nilai rubrik mahasiswa", order=0, owner=kaprodi,
            status="belum_siap", deadline_kind="fixed", fixed_date=far,
            resolved_deadline=far,
            explanation_what="Menilai pekerjaan mahasiswa memakai rubrik.",
            explanation_why="Skor rubrik menjadi bukti ketercapaian.",
            explanation_who="Kaprodi",
            explanation_when=f"Jatuh tempo {far:%d %b %Y}.",
            explanation_how="Masukkan skor untuk setiap kriteria rubrik.",
            explanation_next="Skor digunakan untuk perhitungan ketercapaian.",
        )
        # Waiting on Others (Diajukan), owned by the demo Kaprodi.
        Task.objects.create(
            milestone=im3, title="Tinjau usulan evaluasi", order=0, owner=kaprodi,
            status="diajukan", deadline_kind="fixed", fixed_date=far,
            resolved_deadline=far,
            explanation_what="Meninjau usulan tindak lanjut dari dosen.",
            explanation_why="Persetujuan diperlukan sebelum tindak lanjut.",
            explanation_who="Kaprodi",
            explanation_when=f"Jatuh tempo {far:%d %b %Y}.",
            explanation_how="Baca usulan lalu setujui atau kembalikan.",
            explanation_next="Persetujuan membuka tugas tindak lanjut.",
        )


def unseed_demo_timeline(apps, schema_editor):
    TimelineTemplate = apps.get_model("timeline", "TimelineTemplate")
    OBECycle = apps.get_model("timeline", "OBECycle")
    OBECycle.objects.filter(name=CYCLE_NAME).delete()
    TimelineTemplate.objects.filter(name=TEMPLATE_NAME).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("timeline", "0001_initial"),
        ("core", "0002_seed_demo_data"),
    ]

    operations = [
        migrations.RunPython(seed_demo_timeline, unseed_demo_timeline),
    ]
