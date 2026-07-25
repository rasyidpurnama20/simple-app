"""Unit tests for the core foundation.

Covers:
- Role switch changes available actions (Requirement 15.2)
- Dev_Banner presence in rendered pages (Requirement 15.3)
- Versioned ConfigRecord behavior (Requirement 18.2)
"""

from __future__ import annotations

import pytest

from core.context_processors import DEV_BANNER_TEXT
from core.models import ConfigRecord, DemoUser, ProgramOfStudy, Role
from core.services import (
    ACTIVE_DEMO_USER_SESSION_KEY,
    ConfigService,
    RoleService,
)


@pytest.fixture
def prodi(db):
    # Use a test-only code so this coexists with the seed-data migration
    # (which creates the "IF" program of study).
    return ProgramOfStudy.objects.create(code="TST", name="Prodi Uji")


@pytest.fixture
def kaprodi(db, prodi):
    return DemoUser.objects.create(name="Kaprodi Demo", role=Role.KAPRODI, prodi=prodi)


@pytest.fixture
def lecturer(db, prodi):
    return DemoUser.objects.create(name="Dosen Demo", role=Role.LECTURER, prodi=prodi)


# --- Requirement 15.2: role switch changes available actions --------------

@pytest.mark.django_db
def test_role_switch_changes_available_actions(kaprodi, lecturer):
    kaprodi_ctx = RoleService.active_context(kaprodi.id)
    lecturer_ctx = RoleService.active_context(lecturer.id)

    kaprodi_labels = {a.label for a in kaprodi_ctx.available_actions}
    lecturer_labels = {a.label for a in lecturer_ctx.available_actions}

    # Each role exposes a non-empty, distinct set of actions.
    assert kaprodi_labels
    assert lecturer_labels
    assert kaprodi_labels != lecturer_labels


@pytest.mark.django_db
def test_switch_role_view_updates_session_and_actions(client, kaprodi, lecturer):
    # Start as kaprodi.
    session = client.session
    session[ACTIVE_DEMO_USER_SESSION_KEY] = kaprodi.id
    session.save()

    resp = client.post("/switch-role/", {"demo_user_id": lecturer.id})
    assert resp.status_code == 302
    assert client.session[ACTIVE_DEMO_USER_SESSION_KEY] == lecturer.id


# --- Requirement 15.3: Dev_Banner is present ------------------------------

@pytest.mark.django_db
def test_dev_banner_present_on_home(client, kaprodi):
    resp = client.get("/")
    assert resp.status_code == 200
    assert DEV_BANNER_TEXT.encode() in resp.content


# --- Requirement 18.2: versioned ConfigRecord behavior --------------------

@pytest.mark.django_db
def test_config_record_is_versioned():
    v1 = ConfigService.set_config("passing_threshold", {"value": 60})
    assert v1.version == 1
    assert v1.is_active is True

    v2 = ConfigService.set_config("passing_threshold", {"value": 70})
    assert v2.version == 2

    # Only the newest version is active.
    active = ConfigService.get_active("passing_threshold")
    assert active.version == 2
    assert active.definition == {"value": 70}

    # Older versions are retained (auditable) and returned newest-first.
    history = ConfigService.history("passing_threshold")
    assert [r.version for r in history] == [2, 1]
    assert ConfigRecord.objects.filter(key="passing_threshold").count() == 2
