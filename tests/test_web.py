import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse


@pytest.mark.django_db
def test_health_and_readiness(client):
    assert client.get(reverse("healthz")).json() == {"status": "ok"}
    assert client.get(reverse("readyz")).json() == {"status": "ready"}


@pytest.mark.django_db
def test_dashboard_requires_login(client):
    response = client.get(reverse("dashboard"))
    assert response.status_code == 302
    assert "/accounts/login/" in response.url


@pytest.mark.django_db
def test_dashboard_and_tasks_are_accessible(client):
    user = get_user_model().objects.create_user(username="lecturer", password="safe-test-password")
    client.force_login(user)
    assert client.get(reverse("dashboard")).status_code == 200
    assert client.get(reverse("my_tasks")).status_code == 200


@pytest.mark.django_db
def test_semantic_analytics_contract(client):
    user = get_user_model().objects.create_user(username="gpm", password="safe-test-password")
    client.force_login(user)
    response = client.get(reverse("semantic-analytics"), {"metric": "attainment", "cohort": "2024"})
    assert response.status_code == 200
    body = response.json()
    required = {
        "schema_version",
        "metric_version",
        "rule_version",
        "filters",
        "denominator",
        "missing_count",
        "warnings",
        "reason_codes",
        "units",
        "dimensions",
        "series",
        "data",
    }
    assert required <= body.keys()
    assert response["ETag"]


@pytest.mark.django_db
def test_semantic_analytics_rejects_unknown_metric(client):
    user = get_user_model().objects.create_user(username="prodi", password="safe-test-password")
    client.force_login(user)
    response = client.get(reverse("semantic-analytics"), {"metric": "secret"})
    assert response.status_code == 400
    assert "error" in response.json()
