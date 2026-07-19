import os
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError


@pytest.mark.django_db
def test_import_rejects_truncated_json_before_writing(tmp_path):
    source = tmp_path / "truncated.json"
    source.write_text('{"schemaVersion":"5.0.0","students":[{"nim":"1"}', encoding="utf-8")
    with pytest.raises(CommandError, match="bukan JSON lengkap"):
        call_command("import_obe_sample", path=source)


@pytest.mark.django_db
def test_full_sample_learning_slice_when_source_is_available():
    source = os.environ.get("OBE_FULL_SAMPLE_PATH")
    if not source:
        pytest.skip("Set OBE_FULL_SAMPLE_PATH untuk acceptance file v5 lengkap")
    call_command("import_obe_sample", path=Path(source), student_limit=0)
    call_command("import_obe_sample", path=Path(source), student_limit=0)

    from obe.assessment.models import AssessmentInstrument, Rubric
    from obe.learning.models import RPSVersion, WeeklyPlan
    from obe.learning.services import validate_rps

    rps = RPSVersion.objects.get(public_id="17237222-a7e1-5fa0-a42d-575473157ba6")
    assert WeeklyPlan.objects.filter(rps=rps).count() == 16
    assert AssessmentInstrument.objects.filter(rps_public_id=rps.public_id).count() == 6
    assert Rubric.objects.count() == 2
    assert validate_rps(rps)["valid"]
