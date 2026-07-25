"""Data_Injection_Tool service layer.

Provides idempotent, logged data injection via keyed ORM upserts.
All database access uses the ORM with parameterized queries (Requirement 17.4).
Every load/reset writes a DataInjectionLog record (Requirement 17.3).
"""

from __future__ import annotations

from django.db import transaction

from core.models import DataInjectionLog, DemoUser, ProgramOfStudy


class InjectionService:
    """Idempotent data injection service (Requirements 17.1-17.4)."""

    @staticmethod
    @transaction.atomic
    def seed_demo_data() -> DataInjectionLog:
        """Seed a full vertical-loop demo scenario.

        Creates: Prodi, DemoUsers, TimelineTemplate, OBECycle, Curriculum
        with CPLs, Courses, RPS with rubrics and scores. Idempotent via
        keyed upserts.
        """
        from curriculum.models import (
            ContributionLevel,
            CourseCPLContribution,
            CPL,
            CPLIndicator,
            Course,
            Curriculum,
            CurriculumStatus,
        )
        from rps.models import (
            AssessmentInstrument,
            CPMK,
            RPS,
            RPSStatus,
            Rubric,
            RubricCriterion,
            RubricLevel,
            Score,
            SubCPMK,
            SubCPMKIndicator,
        )
        from timeline.models import (
            ChecklistItem,
            Milestone,
            OBECycle,
            Phase,
            Task,
            TaskDependency,
            TaskStatus,
            TimelineInstance,
            TimelineTemplate,
        )
        from attainment.models import CalculationFormula, FormulaLevel

        # 1. Program of Study
        prodi, _ = ProgramOfStudy.objects.update_or_create(
            code="TI-S1",
            defaults={"name": "Teknik Informatika", "faculty": "Fakultas Teknik"},
        )

        # 2. Demo users
        kaprodi, _ = DemoUser.objects.update_or_create(
            name="Dr. Budi Santoso",
            defaults={"role": "kaprodi", "prodi": prodi},
        )
        lecturer, _ = DemoUser.objects.update_or_create(
            name="Ibu Sari Dewi, M.Kom.",
            defaults={"role": "lecturer", "prodi": prodi},
        )

        # 3. Timeline Template
        template, _ = TimelineTemplate.objects.update_or_create(
            name="Template Siklus OBE Standar",
            defaults={"description": "Template standar untuk satu siklus OBE lengkap."},
        )
        # Template phases
        phase1, _ = Phase.objects.update_or_create(
            template=template, name="Perencanaan",
            defaults={"order": 1},
        )
        phase2, _ = Phase.objects.update_or_create(
            template=template, name="Pelaksanaan",
            defaults={"order": 2},
        )
        phase3, _ = Phase.objects.update_or_create(
            template=template, name="Evaluasi",
            defaults={"order": 3},
        )
        ms1, _ = Milestone.objects.update_or_create(
            phase=phase1, name="Kurikulum Siap",
            defaults={"order": 1},
        )
        ms2, _ = Milestone.objects.update_or_create(
            phase=phase2, name="RPS Selesai",
            defaults={"order": 1},
        )
        ms3, _ = Milestone.objects.update_or_create(
            phase=phase3, name="Perhitungan Capaian",
            defaults={"order": 1},
        )
        t1, _ = Task.objects.update_or_create(
            milestone=ms1, title="Susun Kurikulum",
            defaults={"owner": kaprodi, "status": TaskStatus.SIAP_DIKERJAKAN, "order": 1,
                       "explanation_what": "Menyusun kurikulum baru.",
                       "explanation_why": "Kurikulum diperlukan sebagai dasar RPS.",
                       "explanation_who": "Kaprodi",
                       "explanation_when": "Minggu pertama semester.",
                       "explanation_how": "Identifikasi CPL dan susun mata kuliah.",
                       "explanation_next": "Setelah kurikulum aktif, susun RPS."},
        )
        t2, _ = Task.objects.update_or_create(
            milestone=ms2, title="Susun RPS",
            defaults={"owner": lecturer, "status": TaskStatus.BELUM_SIAP, "order": 1,
                       "explanation_what": "Menyusun RPS lengkap dengan rubrik.",
                       "explanation_why": "RPS diperlukan untuk penilaian capaian.",
                       "explanation_who": "Dosen Pengampu",
                       "explanation_when": "Setelah kurikulum aktif.",
                       "explanation_how": "Definisikan CPMK, rubrik, dan instrumen.",
                       "explanation_next": "Setelah RPS selesai, input nilai."},
        )
        t3, _ = Task.objects.update_or_create(
            milestone=ms3, title="Hitung Capaian",
            defaults={"owner": kaprodi, "status": TaskStatus.BELUM_SIAP, "order": 1,
                       "explanation_what": "Menjalankan perhitungan capaian CPL.",
                       "explanation_why": "Mengetahui gap antara capaian dan target.",
                       "explanation_who": "Kaprodi",
                       "explanation_when": "Akhir semester.",
                       "explanation_how": "Jalankan perhitungan melalui workspace Attainment.",
                       "explanation_next": "Evaluasi gap dan buat rencana perbaikan."},
        )
        # Dependencies
        TaskDependency.objects.update_or_create(
            predecessor=t1, successor=t2,
            defaults={"kind": "hard"},
        )
        TaskDependency.objects.update_or_create(
            predecessor=t2, successor=t3,
            defaults={"kind": "hard"},
        )

        # 4. OBE Cycle with instance
        cycle, _ = OBECycle.objects.update_or_create(
            name="Siklus OBE 2024/2025",
            defaults={
                "academic_year": "2024/2025",
                "prodi": prodi,
                "owner": kaprodi,
                "creator": kaprodi,
                "status": "active",
            },
        )
        instance, _ = TimelineInstance.objects.update_or_create(
            cycle=cycle,
            defaults={"template": template},
        )
        # Instance phases (for the running cycle)
        ip1, _ = Phase.objects.update_or_create(
            instance=instance, name="Perencanaan",
            defaults={"order": 1},
        )
        ip2, _ = Phase.objects.update_or_create(
            instance=instance, name="Pelaksanaan",
            defaults={"order": 2},
        )
        ip3, _ = Phase.objects.update_or_create(
            instance=instance, name="Evaluasi",
            defaults={"order": 3},
        )
        ims1, _ = Milestone.objects.update_or_create(
            phase=ip1, name="Kurikulum Siap",
            defaults={"order": 1},
        )
        ims2, _ = Milestone.objects.update_or_create(
            phase=ip2, name="RPS Selesai",
            defaults={"order": 1},
        )
        ims3, _ = Milestone.objects.update_or_create(
            phase=ip3, name="Perhitungan Capaian",
            defaults={"order": 1},
        )
        it1, _ = Task.objects.update_or_create(
            milestone=ims1, title="Susun Kurikulum",
            defaults={"owner": kaprodi, "status": TaskStatus.SELESAI, "is_complete": True, "order": 1,
                       "explanation_what": "Menyusun kurikulum baru.",
                       "explanation_why": "Kurikulum diperlukan sebagai dasar RPS.",
                       "explanation_who": "Kaprodi",
                       "explanation_when": "Minggu pertama semester.",
                       "explanation_how": "Identifikasi CPL dan susun mata kuliah.",
                       "explanation_next": "Setelah kurikulum aktif, susun RPS."},
        )
        it2, _ = Task.objects.update_or_create(
            milestone=ims2, title="Susun RPS",
            defaults={"owner": lecturer, "status": TaskStatus.DIKERJAKAN, "order": 1,
                       "explanation_what": "Menyusun RPS lengkap dengan rubrik.",
                       "explanation_why": "RPS diperlukan untuk penilaian capaian.",
                       "explanation_who": "Dosen Pengampu",
                       "explanation_when": "Setelah kurikulum aktif.",
                       "explanation_how": "Definisikan CPMK, rubrik, dan instrumen.",
                       "explanation_next": "Setelah RPS selesai, input nilai."},
        )
        it3, _ = Task.objects.update_or_create(
            milestone=ims3, title="Hitung Capaian",
            defaults={"owner": kaprodi, "status": TaskStatus.BELUM_SIAP, "order": 1,
                       "explanation_what": "Menjalankan perhitungan capaian CPL.",
                       "explanation_why": "Mengetahui gap antara capaian dan target.",
                       "explanation_who": "Kaprodi",
                       "explanation_when": "Akhir semester.",
                       "explanation_how": "Jalankan perhitungan melalui workspace Attainment.",
                       "explanation_next": "Evaluasi gap dan buat rencana perbaikan."},
        )
        TaskDependency.objects.update_or_create(
            predecessor=it1, successor=it2,
            defaults={"kind": "hard"},
        )
        TaskDependency.objects.update_or_create(
            predecessor=it2, successor=it3,
            defaults={"kind": "hard"},
        )

        # 5. Curriculum with CPLs
        curriculum, _ = Curriculum.objects.update_or_create(
            name="Kurikulum TI 2024",
            defaults={
                "description": "Kurikulum Teknik Informatika berbasis OBE",
                "year": "2024",
                "prodi": prodi,
                "owner": kaprodi,
                "creator": kaprodi,
                "status": CurriculumStatus.ACTIVE,
            },
        )
        cpl1, _ = CPL.objects.update_or_create(
            curriculum=curriculum, code="CPL-01",
            defaults={"description": "Mampu menerapkan pemikiran komputasional",
                      "prodi": prodi, "owner": kaprodi, "creator": kaprodi,
                      "status": CurriculumStatus.ACTIVE},
        )
        cpl2, _ = CPL.objects.update_or_create(
            curriculum=curriculum, code="CPL-02",
            defaults={"description": "Mampu merancang solusi berbasis teknologi informasi",
                      "prodi": prodi, "owner": kaprodi, "creator": kaprodi,
                      "status": CurriculumStatus.ACTIVE},
        )
        # CPL Indicators
        ind1, _ = CPLIndicator.objects.update_or_create(
            cpl=cpl1, code="IK-01-01",
            defaults={"description": "Mengidentifikasi masalah komputasional", "target_value": 70},
        )
        ind2, _ = CPLIndicator.objects.update_or_create(
            cpl=cpl1, code="IK-01-02",
            defaults={"description": "Merancang algoritma penyelesaian", "target_value": 70},
        )
        ind3, _ = CPLIndicator.objects.update_or_create(
            cpl=cpl2, code="IK-02-01",
            defaults={"description": "Merancang arsitektur sistem", "target_value": 75},
        )

        # 6. Courses
        course1, _ = Course.objects.update_or_create(
            curriculum=curriculum, code="IF101",
            defaults={"name": "Algoritma dan Pemrograman", "credits": 4,
                      "prodi": prodi, "owner": lecturer, "creator": lecturer,
                      "status": CurriculumStatus.ACTIVE},
        )
        course2, _ = Course.objects.update_or_create(
            curriculum=curriculum, code="IF201",
            defaults={"name": "Rekayasa Perangkat Lunak", "credits": 3,
                      "prodi": prodi, "owner": lecturer, "creator": lecturer,
                      "status": CurriculumStatus.ACTIVE},
        )

        # Course -> CPL contributions
        CourseCPLContribution.objects.update_or_create(
            course=course1, cpl=cpl1,
            defaults={"contribution_level": ContributionLevel.MASTER},
        )
        CourseCPLContribution.objects.update_or_create(
            course=course1, cpl=cpl2,
            defaults={"contribution_level": ContributionLevel.INTRODUCE},
        )
        CourseCPLContribution.objects.update_or_create(
            course=course2, cpl=cpl2,
            defaults={"contribution_level": ContributionLevel.MASTER},
        )

        # 7. RPS with rubrics and scores
        rps1, _ = RPS.objects.update_or_create(
            course=course1, curriculum=curriculum, class_name="A", period="2024/Ganjil",
            defaults={"prodi": prodi, "owner": lecturer, "creator": lecturer,
                      "status": RPSStatus.SUBMITTED},
        )
        cpmk1, _ = CPMK.objects.update_or_create(
            rps=rps1, code="CPMK-01",
            defaults={"description": "Memahami dan menerapkan algoritma dasar"},
        )
        cpmk1.derived_from.set([cpl1])

        sub_cpmk1, _ = SubCPMK.objects.update_or_create(
            cpmk=cpmk1, code="Sub-CPMK-01",
            defaults={"description": "Implementasi sorting dan searching"},
        )
        sub_ind1, _ = SubCPMKIndicator.objects.update_or_create(
            sub_cpmk=sub_cpmk1, code="SI-01",
            defaults={"description": "Mampu mengimplementasikan sorting"},
        )

        instr1, _ = AssessmentInstrument.objects.update_or_create(
            rps=rps1, name="Tugas Pemrograman",
            defaults={"description": "Tugas pemrograman algoritma",
                      "prodi": prodi, "owner": lecturer, "creator": lecturer,
                      "status": RPSStatus.SUBMITTED},
        )
        rubric1, _ = Rubric.objects.update_or_create(
            instrument=instr1,
            defaults={"name": "Rubrik Tugas Pemrograman",
                      "prodi": prodi, "owner": lecturer, "creator": lecturer,
                      "status": RPSStatus.SUBMITTED},
        )
        crit1, _ = RubricCriterion.objects.update_or_create(
            rubric=rubric1, name="Ketepatan Algoritma",
            defaults={"weight": 60, "order": 1},
        )
        crit2, _ = RubricCriterion.objects.update_or_create(
            rubric=rubric1, name="Kualitas Kode",
            defaults={"weight": 40, "order": 2},
        )
        crit1.mapped_indicators.set([sub_ind1])

        # Levels
        RubricLevel.objects.update_or_create(
            criterion=crit1, label="Sangat Baik", defaults={"score": 90, "order": 1})
        RubricLevel.objects.update_or_create(
            criterion=crit1, label="Baik", defaults={"score": 75, "order": 2})
        RubricLevel.objects.update_or_create(
            criterion=crit1, label="Cukup", defaults={"score": 60, "order": 3})
        RubricLevel.objects.update_or_create(
            criterion=crit2, label="Sangat Baik", defaults={"score": 90, "order": 1})
        RubricLevel.objects.update_or_create(
            criterion=crit2, label="Baik", defaults={"score": 75, "order": 2})
        RubricLevel.objects.update_or_create(
            criterion=crit2, label="Cukup", defaults={"score": 60, "order": 3})

        # Scores (demo students)
        for student, val1, val2 in [("Mahasiswa-A", 85, 80), ("Mahasiswa-B", 72, 68), ("Mahasiswa-C", 90, 85)]:
            Score.objects.update_or_create(
                criterion=crit1, student_proxy=student,
                defaults={"value": val1},
            )
            Score.objects.update_or_create(
                criterion=crit2, student_proxy=student,
                defaults={"value": val2},
            )

        # 8. Calculation Formula
        CalculationFormula.objects.update_or_create(
            name="weighted_average", version=1,
            defaults={
                "level": FormulaLevel.CPL,
                "definition": {"method": "weighted_average", "description": "Rata-rata tertimbang berdasarkan bobot kriteria"},
                "is_active": True,
            },
        )

        # Log the injection
        log = DataInjectionLog.objects.create(
            operation=DataInjectionLog.Operation.LOAD,
            command="seed_demo_data",
            summary="Seeded full vertical-loop demo scenario: prodi, users, "
                    "template, cycle, curriculum, CPLs, courses, RPS, rubrics, scores.",
            record_count=50,
        )
        return log

    @staticmethod
    @transaction.atomic
    def reset_demo_data() -> DataInjectionLog:
        """Reset all demo data (for testing idempotency)."""
        from curriculum.models import Curriculum, Course, CPL, CPLIndicator, CourseCPLContribution
        from rps.models import RPS, CPMK, SubCPMK, SubCPMKIndicator, AssessmentInstrument, Rubric, Score
        from timeline.models import OBECycle, TimelineTemplate, TimelineInstance
        from attainment.models import AttainmentResult, CalculationFormula

        AttainmentResult.objects.all().delete()
        Score.objects.all().delete()
        Rubric.objects.all().delete()
        AssessmentInstrument.objects.all().delete()
        SubCPMKIndicator.objects.all().delete()
        SubCPMK.objects.all().delete()
        CPMK.objects.all().delete()
        RPS.objects.all().delete()
        CourseCPLContribution.objects.all().delete()
        Course.objects.all().delete()
        CPLIndicator.objects.all().delete()
        CPL.objects.all().delete()
        Curriculum.objects.all().delete()
        TimelineInstance.objects.all().delete()
        OBECycle.objects.all().delete()
        TimelineTemplate.objects.all().delete()
        CalculationFormula.objects.all().delete()

        log = DataInjectionLog.objects.create(
            operation=DataInjectionLog.Operation.RESET,
            command="reset_demo_data",
            summary="Reset all demo data.",
            record_count=0,
        )
        return log
