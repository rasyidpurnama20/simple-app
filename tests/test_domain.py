from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone

from obe.ai.gateway import AIDisabled, complete
from obe.identity.models import RoleAssignment
from obe.identity.services import can
from obe.shared.models import AuditEvent


@pytest.mark.django_db
def test_assignment_permission_and_expiry():
    User = get_user_model()
    granter = User.objects.create_user("system")
    user = User.objects.create_user("lecturer")
    assignment = RoleAssignment.objects.create(
        user=user,
        role="pengampu",
        scope_type="course",
        scope_id="IF101",
        actions=["rps.edit"],
        granted_by=granter,
    )
    assert can(user, "rps.edit", scope_type="course", scope_id="IF101")
    assignment.expires_at = timezone.now() - timedelta(seconds=1)
    assignment.save(update_fields=["expires_at"])
    assert not can(user, "rps.edit", scope_type="course", scope_id="IF101")


@pytest.mark.django_db
def test_self_assignment_is_rejected():
    user = get_user_model().objects.create_user("prodi")
    assignment = RoleAssignment(user=user, role="prodi", actions=["*"], granted_by=user)
    with pytest.raises(ValidationError):
        assignment.full_clean()


@pytest.mark.django_db
def test_audit_is_append_only():
    event = AuditEvent.objects.create(
        action="create", object_type="course", object_id="1", summary="created"
    )
    event.summary = "changed"
    with pytest.raises(ValidationError):
        event.save()
    with pytest.raises(ValidationError):
        event.delete()


def test_ai_off_is_safe(settings):
    settings.OBE_AI_ENABLED = False
    with pytest.raises(AIDisabled):
        complete(model_alias="local-small", messages=[], data_class="internal")
