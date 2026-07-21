import pytest
from django.contrib.auth import get_user_model
from django.test import Client, override_settings
from django.urls import reverse

from obe.identity.models import RoleAssignment


def grant(user, *actions):
    granter = get_user_model().objects.create_user(username=f"granter-{user.username}")
    RoleAssignment.objects.create(
        user=user,
        role="gpm",
        scope_type="global",
        scope_id="*",
        actions=list(actions),
        granted_by=granter,
    )


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
@override_settings(CSRF_TRUSTED_ORIGINS=["http://localhost:8000"])
def test_login_accepts_browser_origin_through_local_nginx():
    password = "safe-test-password"
    get_user_model().objects.create_user(username="local-demo", password=password)
    client = Client(enforce_csrf_checks=True)
    login_url = reverse("login")

    login_page = client.get(login_url, HTTP_HOST="localhost:8000")
    csrf_token = login_page.cookies["csrftoken"].value
    response = client.post(
        login_url,
        {
            "username": "local-demo",
            "password": password,
            "csrfmiddlewaretoken": csrf_token,
        },
        HTTP_HOST="localhost:8000",
        HTTP_ORIGIN="http://localhost:8000",
        HTTP_REFERER="http://localhost:8000/accounts/login/",
        REMOTE_ADDR="192.0.2.44",
    )

    assert response.status_code == 302
    assert response.url == reverse("dashboard")


@pytest.mark.django_db
def test_dashboard_and_tasks_are_accessible(client):
    user = get_user_model().objects.create_user(username="lecturer", password="safe-test-password")
    client.force_login(user)
    assert client.get(reverse("dashboard")).status_code == 200
    assert client.get(reverse("my_tasks")).status_code == 200
    assert client.get(reverse("curriculum_catalog")).status_code == 200
    assert client.get(reverse("my_progress")).status_code == 200


@pytest.mark.django_db
def test_semantic_analytics_contract(client):
    user = get_user_model().objects.create_user(username="gpm", password="safe-test-password")
    grant(user, "analytics.view")
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
    grant(user, "analytics.view")
    client.force_login(user)
    response = client.get(reverse("semantic-analytics"), {"metric": "secret"})
    assert response.status_code == 400
    assert "error" in response.json()


@pytest.mark.django_db
def test_seeded_semantic_analytics_returns_program_cpl(client, monkeypatch):
    from django.core.management import call_command

    monkeypatch.setenv("OBE_DEMO_PASSWORD", "test-demo-password")
    call_command("seed_demo")
    client.force_login(get_user_model().objects.get(username="gpm"))
    response = client.get(reverse("semantic-analytics"), {"metric": "attainment"})
    assert response.status_code == 200
    body = response.json()
    assert len(body["data"]) == 12
    assert body["reason_codes"] == []
    assert {row["outcome"] for row in body["data"]} == {f"CPL{index:02d}" for index in range(1, 13)}
    assert all(row["formula_version"].startswith("sample-v5/") for row in body["data"])
