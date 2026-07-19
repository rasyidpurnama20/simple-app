import json

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command

from obe.academic_lifecycle.models import AcademicResult, StudentProfile, TaskInstance
from obe.assessment.models import AttainmentSnapshot
from obe.curriculum.models import Course, CurriculumEdge, CurriculumVersion, Outcome
from obe.curriculum.services import allocation_report, catalog_report, traceability_report


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
    assert sum(Outcome.objects.filter(kind="BK").values_list("weight", flat=True)) == 100
    assert Course.objects.count() == 77
    assert Course.objects.get(code="MIK1624101").name == "Dasar Sistem"
    assert sum(Course.objects.filter(required=True).values_list("credits", flat=True)) == 129
    assert sum(Course.objects.filter(required=False).values_list("credits", flat=True)) == 90
    curriculum = CurriculumVersion.objects.get(program_code="S1-INFORMATIKA", version=1)
    source = json.loads(
        (settings.BASE_DIR / "fixtures/sample-data-2020-2026-obe-spec-v5.compact.json").read_text()
    )
    for source_key, kind in (
        ("graduateProfiles", "PL"),
        ("cpl", "CPL"),
        ("knowledgeAreas", "BK"),
        ("cpmk", "CPMK"),
    ):
        assert list(
            Outcome.objects.filter(curriculum=curriculum, kind=kind)
            .order_by("code")
            .values_list("code", "description")
        ) == sorted(
            (item["id"], item.get("description") or item.get("name") or item["id"])
            for item in source[source_key]
        )
    assert curriculum.status == "review"
    assert curriculum.approval_snapshot["credit_policy"]["activationValid"] is False
    allocations = allocation_report(curriculum)
    assert allocations["totals_valid"] is True
    assert allocations["valid"] is False
    assert allocations["unapproved"]
    catalog = catalog_report(curriculum)
    assert catalog["credit_valid"] is False
    assert catalog["required_credits"] == 129
    traceability = traceability_report(curriculum)
    assert traceability["valid"] is False
    assert traceability["orphan"] == []
    assert {
        tuple(finding["node"])
        for finding in traceability["gaps"]
        if finding["missing"] == "inbound"
    } == {("CPMK", "CPMK22"), ("CPMK", "CPMK27")}
    assert not CurriculumEdge.objects.filter(allocation_method="equal-split").exists()
    assert set(
        CurriculumEdge.objects.filter(curriculum=curriculum).values_list(
            "source_type", "target_type"
        )
    ) == {
        ("PL", "CPL"),
        ("CPL", "BK"),
        ("CPL", "CPMK"),
        ("BK", "COURSE"),
        ("COURSE", "CPMK"),
    }
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
