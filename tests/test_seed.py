import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from obe.academic_lifecycle.models import AcademicResult, StudentProfile, TaskInstance
from obe.assessment.models import AttainmentSnapshot
from obe.curriculum.models import Course, CurriculumEdge, CurriculumVersion, Outcome
from obe.curriculum.services import allocation_report


@pytest.mark.django_db
def test_seed_is_idempotent_and_complete(monkeypatch):
    monkeypatch.setenv("OBE_DEMO_PASSWORD", "test-demo-password")
    legacy = CurriculumVersion.objects.create(
        program_code="IF",
        version=1,
        name="Kurikulum Informatika OBE",
        cohort_from=2024,
    )
    call_command("seed_demo")
    call_command("seed_demo")
    legacy.refresh_from_db()
    assert legacy.status == "archived"
    assert Outcome.objects.filter(kind="PL").count() == 5
    assert Outcome.objects.filter(kind="CPL").count() == 12
    assert Outcome.objects.filter(kind="BK").count() == 18
    assert Outcome.objects.filter(kind="CPMK").count() == 31
    assert Course.objects.count() == 77
    assert Course.objects.get(code="MIK1624101").name == "Dasar Sistem"
    assert sum(Course.objects.filter(required=True).values_list("credits", flat=True)) == 129
    assert sum(Course.objects.filter(required=False).values_list("credits", flat=True)) == 90
    curriculum = CurriculumVersion.objects.get(program_code="S1-INFORMATIKA", version=1)
    assert curriculum.status == "review"
    assert curriculum.approval_snapshot["credit_policy"]["activationValid"] is False
    assert allocation_report(curriculum)["valid"] is True
    assert CurriculumEdge.objects.filter(curriculum=curriculum).exists()
    assert AttainmentSnapshot.objects.filter(scope_type="program").count() == 12
    assert all(
        len(value) <= AttainmentSnapshot._meta.get_field("formula_version").max_length
        for value in AttainmentSnapshot.objects.values_list("formula_version", flat=True)
    )
    assert StudentProfile.objects.count() == 4
    assert AcademicResult.objects.count() == 212
    assert TaskInstance.objects.count() == 4
    mahasiswa = get_user_model().objects.get(username="mahasiswa")
    assert mahasiswa.studentprofile.results.exists()
