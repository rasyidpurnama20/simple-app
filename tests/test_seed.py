import pytest
from django.core.management import call_command

from obe.curriculum.models import Course, Outcome


@pytest.mark.django_db
def test_seed_is_idempotent_and_complete(monkeypatch):
    monkeypatch.setenv("OBE_DEMO_PASSWORD", "test-demo-password")
    call_command("seed_demo")
    call_command("seed_demo")
    assert Outcome.objects.filter(kind="PL").count() == 5
    assert Outcome.objects.filter(kind="CPL").count() == 12
    assert Outcome.objects.filter(kind="BK").count() == 18
    assert Outcome.objects.filter(kind="CPMK").count() == 31
    assert Course.objects.count() == 77
    assert sum(Course.objects.filter(required=True).values_list("credits", flat=True)) == 126
