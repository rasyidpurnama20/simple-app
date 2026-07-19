import json
from datetime import date

import pytest
from django.core.exceptions import ValidationError

from obe.curriculum.models import Course, CurriculumEdge, CurriculumVersion, Outcome
from obe.curriculum.package import (
    export_csv_bundle,
    export_json_package,
    import_csv_bundle,
    import_json_package,
)
from obe.curriculum.services import (
    activate,
    allocation_report,
    approve_allocations,
    approve_curriculum,
    catalog_report,
    clone_curriculum,
    course_progress,
    curriculum_diff,
    impacted_nodes,
    rollback_activation,
    submit_for_review,
    trace_paths,
    traceability_report,
)
from obe.shared.services import ActorContext


def actor(identifier: str) -> ActorContext:
    return ActorContext(identifier, identifier, "curriculum")


def curriculum_package(program_code: str = "TEST") -> CurriculumVersion:
    curriculum = CurriculumVersion.objects.create(
        program_code=program_code,
        program_name="Program Uji",
        name="Kurikulum Uji",
        version=1,
        curriculum_year=2024,
        cohort_from=2024,
        effective_from=date(2024, 8, 1),
        created_by_actor_id="maker",
        updated_by_actor_id="maker",
    )
    for kind, code in (("PL", "PL01"), ("CPL", "CPL01"), ("CPMK", "CPMK01")):
        Outcome.objects.create(
            curriculum=curriculum,
            kind=kind,
            code=code,
            name=code,
            description=f"Deskripsi {code}",
            weight=100,
            target=75,
        )
    Outcome.objects.create(
        curriculum=curriculum,
        kind="BK",
        code="BKU01",
        name="Bahan Kajian",
        description="Bahan kajian uji",
        category="Utama",
        depth=6,
        knowledge_depth=6,
        skill_depth=5,
        attitude_depth=4,
        owner_role="PRODI",
        weight=100,
    )
    for code, name, credits, required, semester in (
        ("W001", "Mata Kuliah Wajib", 126, True, 1),
        ("P001", "Mata Kuliah Pilihan", 18, False, 7),
    ):
        Course.objects.create(
            curriculum=curriculum,
            code=code,
            name=name,
            credits=credits,
            required=required,
            recommended_semester=semester,
            term="odd",
        )
    edges = (
        ("PL", "PL01", "CPL", "CPL01", 100),
        ("CPL", "CPL01", "BK", "BKU01", 100),
        ("CPL", "CPL01", "CPMK", "CPMK01", 100),
        ("BK", "BKU01", "COURSE", "W001", 50),
        ("BK", "BKU01", "COURSE", "P001", 50),
        ("COURSE", "W001", "CPMK", "CPMK01", 100),
        ("COURSE", "P001", "CPMK", "CPMK01", 100),
    )
    for source_type, source_id, target_type, target_id, weight in edges:
        CurriculumEdge.objects.create(
            curriculum=curriculum,
            source_type=source_type,
            source_id=source_id,
            target_type=target_type,
            target_id=target_id,
            allocation_weight=weight,
            allocation_method="explicit",
        )
    return curriculum


@pytest.mark.django_db
def test_curriculum_lifecycle_clone_diff_activation_and_rollback():
    curriculum = curriculum_package()
    assert catalog_report(curriculum, strict_counts=False)["valid"]
    assert traceability_report(curriculum)["valid"]
    assert not allocation_report(curriculum)["valid"]

    approve_allocations(curriculum, actor=actor("allocation-approver"), approval_reference="SK-1")
    reviewed = submit_for_review(curriculum, actor=actor("reviewer"))
    approved = approve_curriculum(
        reviewed,
        actor=actor("approver"),
        documents=[{"type": "SK", "reference": "SK-1"}],
        strict_catalog=False,
    )
    with pytest.raises(ValidationError, match="activator"):
        activate(
            approved,
            actor=actor("approver"),
            integrity_verified=True,
            strict_catalog=False,
        )
    active = activate(
        approved,
        actor=actor("activator"),
        integrity_verified=True,
        strict_catalog=False,
    )
    assert active.status == "active" and len(active.checksum) == 64
    active.name = "Mutasi terlarang"
    with pytest.raises(ValidationError, match="immutable"):
        active.save()
    with pytest.raises(ValidationError, match="immutable"):
        Outcome.objects.create(
            curriculum=active,
            kind="CPL",
            code="CPL02",
            name="CPL02",
            description="Mutasi terlarang",
        )

    clone = clone_curriculum(active, actor=actor("maker-v2"), effective_from=date(2025, 8, 1))
    assert clone.status == "draft" and clone.version == 2
    assert clone.outcomes.count() == active.outcomes.count()
    changed_course = clone.courses.get(code="P001")
    changed_course.name = "Pilihan Versi Dua"
    changed_course.save()
    assert curriculum_diff(active, clone)["changed"]

    approve_allocations(clone, actor=actor("allocation-v2"), approval_reference="SK-2")
    clone = submit_for_review(clone, actor=actor("reviewer-v2"))
    clone = approve_curriculum(
        clone,
        actor=actor("approver-v2"),
        documents=[{"type": "SK", "reference": "SK-2"}],
        strict_catalog=False,
    )
    clone = activate(
        clone,
        actor=actor("activator-v2"),
        integrity_verified=True,
        strict_catalog=False,
    )
    active.refresh_from_db()
    assert active.status == "archived" and clone.status == "active"
    restored = rollback_activation(clone, active, actor=actor("rollback-operator"))
    clone.refresh_from_db()
    assert restored.status == "active" and clone.status == "archived"


@pytest.mark.django_db
def test_traceability_validation_paths_and_course_progress():
    curriculum = curriculum_package("TRACE")
    approve_allocations(curriculum, actor=actor("approver"), approval_reference="MAP-1")
    assert allocation_report(curriculum)["valid"]
    assert trace_paths(curriculum, node_type="PL", node_id="PL01")[0][0] == ("PL", "PL01")
    reverse = trace_paths(curriculum, node_type="CPMK", node_id="CPMK01", reverse=True)
    assert any(("PL", "PL01") in path for path in reverse)
    assert ("CPMK", "CPMK01") in impacted_nodes(curriculum, node_type="PL", node_id="PL01")

    progress = course_progress(
        curriculum,
        {"W001": {"passed": True}, "P001": {"attempts": 2}},
    )
    assert progress["earned_required"] == 126
    assert progress["remaining_elective"] == 18
    assert {row["status"] for row in progress["courses"]} == {"passed", "repeat"}

    duplicate = CurriculumEdge.objects.create(
        curriculum=curriculum,
        source_type="PL",
        source_id="PL01",
        target_type="CPL",
        target_id="CPL01",
        allocation_weight=1,
        approval_reference="MAP-1",
        version=2,
    )
    assert traceability_report(curriculum)["duplicates"]
    duplicate.delete()

    edge = curriculum.edges.get(source_type="PL", source_id="PL01")
    edge.target_id = "CPL-MISSING"
    edge.save()
    report = traceability_report(curriculum)
    assert not report["valid"] and report["orphan"]

    with pytest.raises(ValidationError, match="Equal split"):
        CurriculumEdge.objects.create(
            curriculum=curriculum,
            source_type="PL",
            source_id="PL01",
            target_type="CPL",
            target_id="CPL02",
            allocation_weight=1,
            allocation_method="equal-split",
        )
    with pytest.raises(ValidationError, match="Self-cycle"):
        CurriculumEdge.objects.create(
            curriculum=curriculum,
            source_type="CPL",
            source_id="CPL01",
            target_type="CPL",
            target_id="CPL01",
            allocation_weight=100,
        )

    course = curriculum.courses.get(code="P001")
    course.prerequisites = ["MISSING"]
    course.save()
    assert catalog_report(curriculum, strict_counts=False)["prerequisite_errors"] == [
        {"course": "P001", "prerequisite": "MISSING", "reason": "orphan"}
    ]


@pytest.mark.django_db
def test_json_and_csv_packages_are_checksum_valid_and_idempotent():
    curriculum = curriculum_package("PACKAGE")
    payload = export_json_package(curriculum)
    imported = import_json_package(payload, actor=actor("importer"))
    assert imported.version == 2 and imported.status == "draft"
    assert import_json_package(payload, actor=actor("importer")).pk == imported.pk

    bundle = export_csv_bundle(curriculum)
    assert import_csv_bundle(bundle, actor=actor("csv-importer")).pk == imported.pk

    tampered = json.loads(payload)
    tampered["curriculum"]["name"] = "Paket berubah"
    with pytest.raises(ValidationError, match="Checksum"):
        import_json_package(tampered, actor=actor("importer"))


@pytest.mark.django_db
def test_failed_activation_rolls_back_state():
    curriculum = curriculum_package("ROLLBACK")
    approve_allocations(curriculum, actor=actor("allocation"), approval_reference="SK-R")
    curriculum = submit_for_review(curriculum, actor=actor("reviewer"))
    curriculum = approve_curriculum(
        curriculum,
        actor=actor("approver"),
        documents=[{"type": "SK", "reference": "SK-R"}],
        strict_catalog=False,
    )
    with pytest.raises(ValidationError, match="Integrity"):
        activate(curriculum, actor=actor("activator"), strict_catalog=False)
    curriculum.refresh_from_db()
    assert curriculum.status == "review" and not curriculum.activated_at
