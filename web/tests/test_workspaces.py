"""Structural and property tests for the UI layer.

Feature: obe-system
Property 26: Wizard steps persist before advancing.
Structural: views contain no business logic, exactly five workspaces.
"""

import inspect

import pytest
from hypothesis import given, settings, strategies as st

from web import views as web_views


@pytest.mark.django_db
class TestProperty26WizardPersist:
    """Feature: obe-system, Property 26: Wizard steps persist before advancing

    Validates: Requirements 16.2, 16.3
    """

    def test_property_26_curriculum_create_persists(self):
        """Creating a curriculum persists data through the service layer."""
        from django.test import RequestFactory

        from core.models import DemoUser, ProgramOfStudy
        from curriculum.models import Curriculum

        prodi = ProgramOfStudy.objects.create(code="WIZ-TEST", name="Test")
        actor = DemoUser.objects.create(name="Actor", role="kaprodi", prodi=prodi)

        factory = RequestFactory()
        request = factory.post("/curriculum/create/", {
            "name": "Kurikulum Wizard Test",
            "year": "2025",
        })
        request.demo_user_id = actor.id
        request.role_context = None

        # Need session
        from django.contrib.sessions.backends.db import SessionStore
        from django.contrib.messages.storage.fallback import FallbackStorage
        request.session = SessionStore()
        request._messages = FallbackStorage(request)

        response = web_views.curriculum_create(request)

        # Curriculum was persisted before redirect (wizard autosave)
        assert Curriculum.objects.filter(name="Kurikulum Wizard Test").exists()


def test_structural_five_workspaces():
    """Structural: exactly five workspaces (Requirement 16.1)."""
    from web.services import _WORKSPACES
    assert len(_WORKSPACES) == 5


def test_structural_views_are_thin():
    """Structural: views call services, no business logic inline."""
    # Views should be short functions (< 30 lines of code)
    view_functions = [
        web_views.home,
        web_views.timeline_workspace,
        web_views.curriculum_workspace,
        web_views.learning_workspace,
        web_views.attainment_workspace,
    ]
    for fn in view_functions:
        source = inspect.getsource(fn)
        lines = [l for l in source.split("\n") if l.strip() and not l.strip().startswith("#")]
        assert len(lines) < 30, f"{fn.__name__} has {len(lines)} non-empty lines (should be thin)"


@pytest.mark.django_db
def test_integration_demo_seeded():
    """Smoke: demo accounts seeded (Requirement 15.1)."""
    from injection.services import InjectionService
    InjectionService.seed_demo_data()

    from core.models import DemoUser
    assert DemoUser.objects.filter(role="kaprodi").exists()
    assert DemoUser.objects.filter(role="lecturer").exists()


@pytest.mark.django_db
def test_smoke_dev_banner_present(client):
    """Smoke: Dev_Banner present in response (Requirement 15.3)."""
    from injection.services import InjectionService
    InjectionService.seed_demo_data()

    response = client.get("/")
    content = response.content.decode()
    assert "dev-banner" in content


@pytest.mark.django_db
def test_smoke_no_auth_enforcement(client):
    """Smoke: no auth enforcement, pages accessible (Requirement 15.4)."""
    from injection.services import InjectionService
    InjectionService.seed_demo_data()

    # All workspace pages accessible without login
    for url in ["/", "/timeline/", "/curriculum/", "/learning/", "/attainment/"]:
        response = client.get(url)
        assert response.status_code == 200, f"Failed for {url}"


@pytest.mark.django_db
def test_smoke_migrations_applied():
    """Smoke: migrations applied, schema correct (Requirement 18.1)."""
    from django.core.management import call_command
    from io import StringIO

    out = StringIO()
    call_command("showmigrations", "--plan", stdout=out)
    output = out.getvalue()
    # All migrations should be applied (marked with [X])
    lines = [l for l in output.split("\n") if l.strip()]
    unapplied = [l for l in lines if "[ ]" in l]
    assert len(unapplied) == 0, f"Unapplied migrations: {unapplied}"
