"""Seed comprehensive demo data for Curriculum, RPS, and Attainment.

This is a DATA migration that creates realistic demo data so all workspaces
show meaningful content on first run. Idempotent via get_or_create.
"""

from decimal import Decimal

from django.db import migrations


def seed_full_demo(apps, schema_editor):
    ProgramOfStudy = apps.get_model("core", "ProgramOfStudy")
    DemoUser = apps.get_model("core", "DemoUser")
    Curriculum = apps.get_model("curriculum", "Curriculum")
    CPL = apps.get_model("curriculum", "CPL")
    CPLIndicator = apps.get_model("curriculum", "CPLIndicator")
    Course = apps.get_model("curriculum", "Course")
    CourseCPLContribution = apps.get_model("curriculum", "CourseCPLContribution")
    RPS = apps.get_model("rps", "RPS")
    CPMK = apps.get_model("rps", "CPMK")
    SubCPMK = apps.get_model("rps", "SubCPMK")
    SubCPMKIndicator = apps.get_model("rps", "SubCPMKIndicator")
    AssessmentInstrument = apps.get_model("rps", "AssessmentInstrument")
    Rubric = apps.get_model("rps", "Rubric")
    RubricCriterion = apps.get_model("rps", "RubricCriterion")
    RubricLevel = apps.get_model("rps", "RubricLevel")
    Score = apps.get_model("rps", "Score")
    CalculationFormula = apps.get_model("attainment", "CalculationFormula")

    prodi = ProgramOfStudy.objects.filter(code="IF").first()
    if prodi is None:
        return

    kaprodi = DemoUser.objects.filter(role="kaprodi").first()
    lecturer = DemoUser.objects.filter(role="lecturer").first()
    if kaprodi is None or lecturer is None:
        return

    # --- 1. Curriculum ---
    curriculum, _ = Curriculum.objects.get_or_create(
        name="Kurikulum Informatika 2024",
        defaults={
            "description": "Kurikulum program studi Teknik Informatika tahun 2024",
            "year": "2024",
            "prodi": prodi,
            "owner": kaprodi,
            "creator": kaprodi,
            "status": "active",
            "version": 1,
        },
    )

    # --- 2. CPLs ---
    cpl_data = [
        ("CPL-1", "Mampu menerapkan pemikiran logis, kritis, sistematis, dan inovatif dalam pengembangan perangkat lunak"),
        ("CPL-2", "Mampu merancang dan mengimplementasikan struktur data dan algoritma yang efisien"),
        ("CPL-3", "Mampu merancang, mengimplementasikan, dan mengelola basis data"),
        ("CPL-4", "Mampu menerapkan metodologi rekayasa perangkat lunak dalam pengembangan sistem"),
    ]
    cpls = {}
    for code, desc in cpl_data:
        cpl, _ = CPL.objects.get_or_create(
            curriculum=curriculum,
            code=code,
            defaults={
                "description": desc,
                "prodi": prodi,
                "owner": kaprodi,
                "creator": kaprodi,
                "status": "active",
                "version": 1,
            },
        )
        cpls[code] = cpl

    # --- 3. CPL Indicators ---
    indicator_data = [
        ("CPL-1", "IK-1.1", "Mampu menganalisis masalah dan merancang solusi algoritmik", Decimal("70.00")),
        ("CPL-1", "IK-1.2", "Mampu menulis kode program yang bersih dan terdokumentasi", Decimal("70.00")),
        ("CPL-2", "IK-2.1", "Mampu memilih dan menerapkan struktur data yang tepat", Decimal("70.00")),
        ("CPL-2", "IK-2.2", "Mampu menganalisis kompleksitas algoritma", Decimal("70.00")),
        ("CPL-3", "IK-3.1", "Mampu merancang skema basis data yang ternormalisasi", Decimal("70.00")),
        ("CPL-3", "IK-3.2", "Mampu menulis query SQL yang efisien", Decimal("70.00")),
        ("CPL-4", "IK-4.1", "Mampu menerapkan proses SDLC dalam proyek", Decimal("70.00")),
        ("CPL-4", "IK-4.2", "Mampu menggunakan tools manajemen proyek perangkat lunak", Decimal("70.00")),
    ]
    indicators = {}
    for cpl_code, ind_code, ind_desc, target in indicator_data:
        ind, _ = CPLIndicator.objects.get_or_create(
            cpl=cpls[cpl_code],
            code=ind_code,
            defaults={
                "description": ind_desc,
                "target_value": target,
            },
        )
        indicators[ind_code] = ind

    # --- 4. Courses ---
    course_data = [
        ("IF101", "Pemrograman Dasar", 3),
        ("IF201", "Struktur Data", 4),
        ("IF301", "Basis Data", 3),
        ("IF401", "Rekayasa Perangkat Lunak", 4),
    ]
    courses = {}
    for code, name, credits in course_data:
        course, _ = Course.objects.get_or_create(
            curriculum=curriculum,
            code=code,
            defaults={
                "name": name,
                "credits": credits,
                "prodi": prodi,
                "owner": kaprodi,
                "creator": kaprodi,
                "status": "active",
                "version": 1,
            },
        )
        courses[code] = course

    # --- 5. CourseCPLContribution mappings ---
    contribution_data = [
        ("IF101", "CPL-1", "Master"),
        ("IF101", "CPL-2", "Introduce"),
        ("IF201", "CPL-2", "Master"),
        ("IF201", "CPL-1", "Reinforce"),
        ("IF301", "CPL-3", "Master"),
        ("IF301", "CPL-4", "Introduce"),
        ("IF401", "CPL-4", "Master"),
        ("IF401", "CPL-3", "Reinforce"),
    ]
    for course_code, cpl_code, level in contribution_data:
        CourseCPLContribution.objects.get_or_create(
            course=courses[course_code],
            cpl=cpls[cpl_code],
            defaults={"contribution_level": level},
        )

    # --- 6. RPS (for IF101 and IF301) ---
    rps1, _ = RPS.objects.get_or_create(
        course=courses["IF101"],
        curriculum=curriculum,
        class_name="A",
        period="Gasal 2024/2025",
        defaults={
            "prodi": prodi,
            "owner": lecturer,
            "creator": lecturer,
            "status": "approved",
            "version": 1,
        },
    )
    rps2, _ = RPS.objects.get_or_create(
        course=courses["IF301"],
        curriculum=curriculum,
        class_name="A",
        period="Gasal 2024/2025",
        defaults={
            "prodi": prodi,
            "owner": lecturer,
            "creator": lecturer,
            "status": "approved",
            "version": 1,
        },
    )

    # --- 7. CPMKs, SubCPMKs, Indicators for each RPS ---
    def create_rps_structure(rps, cpl_list, prefix):
        """Create 2 CPMKs, each with 1 SubCPMK, 1 indicator per SubCPMK."""
        cpmks = []
        sub_indicators = []
        for i, cpl in enumerate(cpl_list, 1):
            cpmk, _ = CPMK.objects.get_or_create(
                rps=rps,
                code=f"{prefix}-CPMK-{i}",
                defaults={"description": f"Capaian pembelajaran mata kuliah {i} untuk {prefix}"},
            )
            # M2M derived_from - handled after creation
            cpmk.derived_from.add(cpl)
            cpmks.append(cpmk)

            sub_cpmk, _ = SubCPMK.objects.get_or_create(
                cpmk=cpmk,
                code=f"{prefix}-Sub-{i}",
                defaults={"description": f"Sub-capaian {i}"},
            )
            sub_ind, _ = SubCPMKIndicator.objects.get_or_create(
                sub_cpmk=sub_cpmk,
                code=f"{prefix}-SI-{i}",
                defaults={"description": f"Indikator sub-CPMK {i}"},
            )
            sub_indicators.append(sub_ind)
        return cpmks, sub_indicators

    cpmks1, sub_inds1 = create_rps_structure(rps1, [cpls["CPL-1"], cpls["CPL-2"]], "IF101")
    cpmks2, sub_inds2 = create_rps_structure(rps2, [cpls["CPL-3"], cpls["CPL-4"]], "IF301")

    # --- 8. Assessment Instruments with Rubrics ---
    def create_instrument_with_rubric(rps, name, sub_indicators, owner):
        """Create instrument, rubric, 2 criteria (50/50 weight), 2 levels each, mapped to indicators."""
        instrument, _ = AssessmentInstrument.objects.get_or_create(
            rps=rps,
            name=name,
            defaults={
                "description": f"Instrumen penilaian: {name}",
                "prodi": rps.prodi,
                "owner": owner,
                "creator": owner,
                "status": "approved",
                "version": 1,
            },
        )
        rubric, _ = Rubric.objects.get_or_create(
            instrument=instrument,
            defaults={
                "name": f"Rubrik {name}",
                "prodi": rps.prodi,
                "owner": owner,
                "creator": owner,
                "status": "approved",
                "version": 1,
            },
        )
        criteria = []
        for i, sub_ind in enumerate(sub_indicators):
            criterion, _ = RubricCriterion.objects.get_or_create(
                rubric=rubric,
                name=f"Kriteria {i+1}: {sub_ind.code}",
                defaults={
                    "weight": Decimal("50.00"),
                    "order": i,
                },
            )
            criterion.mapped_indicators.add(sub_ind)
            criteria.append(criterion)

            # 2 levels per criterion
            RubricLevel.objects.get_or_create(
                criterion=criterion,
                label="Baik",
                defaults={"score": Decimal("85.00"), "order": 0},
            )
            RubricLevel.objects.get_or_create(
                criterion=criterion,
                label="Cukup",
                defaults={"score": Decimal("65.00"), "order": 1},
            )
        return instrument, rubric, criteria

    inst1, rub1, criteria1 = create_instrument_with_rubric(
        rps1, "Tugas Pemrograman", sub_inds1, lecturer
    )
    inst2, rub2, criteria2 = create_instrument_with_rubric(
        rps2, "Tugas Basis Data", sub_inds2, lecturer
    )

    # --- 9. Scores ---
    students = ["MHS001", "MHS002", "MHS003", "MHS004", "MHS005"]
    # Scores for RPS 1 criteria
    score_values_1 = [
        [Decimal("80.00"), Decimal("75.00"), Decimal("85.00"), Decimal("70.00"), Decimal("78.00")],
        [Decimal("72.00"), Decimal("68.00"), Decimal("80.00"), Decimal("65.00"), Decimal("75.00")],
    ]
    for crit_idx, criterion in enumerate(criteria1):
        for st_idx, student in enumerate(students):
            Score.objects.get_or_create(
                criterion=criterion,
                student_proxy=student,
                defaults={"value": score_values_1[crit_idx][st_idx]},
            )

    # Scores for RPS 2 criteria
    score_values_2 = [
        [Decimal("70.00"), Decimal("65.00"), Decimal("78.00"), Decimal("72.00"), Decimal("80.00")],
        [Decimal("68.00"), Decimal("72.00"), Decimal("75.00"), Decimal("70.00"), Decimal("65.00")],
    ]
    for crit_idx, criterion in enumerate(criteria2):
        for st_idx, student in enumerate(students):
            Score.objects.get_or_create(
                criterion=criterion,
                student_proxy=student,
                defaults={"value": score_values_2[crit_idx][st_idx]},
            )

    # --- 10. CalculationFormula ---
    CalculationFormula.objects.get_or_create(
        name="weighted_average",
        version=1,
        defaults={
            "level": "cpl",
            "definition": {"method": "weighted_average"},
            "is_active": True,
        },
    )


def unseed_full_demo(apps, schema_editor):
    """Reverse: delete seeded demo data (best effort)."""
    Curriculum = apps.get_model("curriculum", "Curriculum")
    RPS = apps.get_model("rps", "RPS")
    CalculationFormula = apps.get_model("attainment", "CalculationFormula")

    # Cascading deletes handle CPLs, courses, contributions, etc.
    Curriculum.objects.filter(name="Kurikulum Informatika 2024").delete()
    RPS.objects.filter(period="Gasal 2024/2025", class_name="A").delete()
    CalculationFormula.objects.filter(name="weighted_average", version=1).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("injection", "__first__"),
        ("core", "0002_seed_demo_data"),
        ("curriculum", "0001_curriculum_models"),
        ("rps", "0001_rps_models"),
        ("attainment", "0001_attainment_models"),
        ("timeline", "0002_seed_demo_timeline"),
    ]

    operations = [
        migrations.RunPython(seed_full_demo, unseed_full_demo),
    ]
