import pytest
from django.core.management import call_command
from django.core.management.base import CommandError


@pytest.mark.django_db
def test_import_rejects_truncated_json_before_writing(tmp_path):
    source = tmp_path / "truncated.json"
    source.write_text('{"schemaVersion":"5.0.0","students":[{"nim":"1"}', encoding="utf-8")
    with pytest.raises(CommandError, match="bukan JSON lengkap"):
        call_command("import_obe_sample", path=source)
