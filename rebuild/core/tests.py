import os

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase, override_settings

from core.roles import ROLES


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class StageZeroTests(TestCase):
    def setUp(self):
        os.environ["STAGE0_DEMO_PASSWORD"] = "test-stage0-password"  # noqa: S105
        call_command("seed_stage0", verbosity=0)

    def tearDown(self):
        os.environ.pop("STAGE0_DEMO_PASSWORD", None)

    def test_health_endpoint_is_public(self):
        response = self.client.get("/healthz/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "stage": 0})

    def test_anonymous_user_is_sent_to_login(self):
        response = self.client.get("/dashboard/")
        self.assertRedirects(response, "/accounts/login/?next=/dashboard/")

    def test_seed_is_idempotent_and_syncs_password_without_duplicate_users(self):
        os.environ["STAGE0_DEMO_PASSWORD"] = "updated-stage0-password"  # noqa: S105
        call_command("seed_stage0", verbosity=0)
        user_model = get_user_model()
        self.assertEqual(user_model.objects.filter(username__in=[r.code for r in ROLES]).count(), 4)
        self.assertEqual(Group.objects.filter(name__in=[r.code for r in ROLES]).count(), 4)
        for role in ROLES:
            user = user_model.objects.get(username=role.code)
            self.assertTrue(user.check_password("updated-stage0-password"))
            self.assertEqual(set(user.groups.values_list("name", flat=True)), {role.code})

    def test_each_role_can_login_and_sees_only_its_identity(self):
        for role in ROLES:
            with self.subTest(role=role.code):
                self.client.logout()
                logged_in = self.client.login(
                    username=role.code,
                    password="test-stage0-password",
                )
                self.assertTrue(logged_in)
                response = self.client.get("/dashboard/")
                self.assertContains(response, role.label)
                self.assertContains(response, role.purpose)
                for other in ROLES:
                    if other != role:
                        self.assertNotContains(response, other.purpose)

    @override_settings(CSRF_COOKIE_SECURE=False, SESSION_COOKIE_SECURE=False)
    def test_logout_requires_post_and_returns_to_login(self):
        self.client.login(username="prodi", password="test-stage0-password")
        self.assertEqual(self.client.get("/accounts/logout/").status_code, 405)
        response = self.client.post("/accounts/logout/")
        self.assertRedirects(response, "/accounts/login/")
