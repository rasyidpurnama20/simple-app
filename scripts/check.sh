#!/bin/sh
set -eu
ruff check .
ruff format --check .
mypy config obe --exclude migrations
python manage.py makemigrations --check --dry-run --settings=config.settings.test
coverage run -m pytest
coverage report
python tests/test_architecture.py
