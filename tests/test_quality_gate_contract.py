import json
from pathlib import Path

from scripts.check_critical_coverage import domain_coverage
from scripts.check_migration_reversibility import irreversible_operations

ROOT = Path(__file__).resolve().parents[1]


def test_ci_keeps_pr03_quality_and_evidence_contract():
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    required = {
        "ruff check .",
        "ruff format --check .",
        "mypy config obe --exclude migrations",
        "makemigrations --check --dry-run",
        "check_migration_reversibility.py",
        "test-report.xml",
        "check_critical_coverage.py",
        "pip-audit",
        "gitleaks/gitleaks-action",
        "sbom-python.json",
        "image-digest.txt",
        "actions/upload-artifact@v7",
    }
    assert required <= {token for token in required if token in workflow}


def test_irreversible_migration_is_rejected(tmp_path):
    migration = tmp_path / "0002_bad.py"
    migration.write_text(
        "from django.db import migrations\n"
        "class Migration(migrations.Migration):\n"
        "    operations = [migrations.RunPython(lambda apps, schema_editor: None)]\n",
        encoding="utf-8",
    )
    assert irreversible_operations(migration)


def test_critical_module_below_threshold_can_be_measured():
    report = {
        "files": {"obe/shared/models.py": {"summary": {"num_statements": 100, "covered_lines": 84}}}
    }
    assert domain_coverage(json.loads(json.dumps(report)), "shared") == 84.0
