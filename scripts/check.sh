#!/bin/sh
set -eu
ruff check .
ruff format --check .
mypy config obe --exclude migrations
python manage.py makemigrations --check --dry-run --settings=config.settings.test
python scripts/check_migration_reversibility.py
python tests/test_architecture.py
coverage run -m pytest --junitxml=test-report.xml
coverage report
coverage xml
coverage json -o coverage.json
python scripts/check_critical_coverage.py coverage.json
