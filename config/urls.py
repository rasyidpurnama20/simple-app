from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from obe.academic_lifecycle.views import my_progress
from obe.identity.views import (
    AuditedLogoutView,
    SecureLoginView,
    SecurePasswordResetConfirmView,
    verify_mfa,
)
from obe.shared.views import dashboard, healthz, readyz

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/login/", SecureLoginView.as_view(), name="login"),
    path("accounts/logout/", AuditedLogoutView.as_view(), name="logout"),
    path("accounts/mfa/", verify_mfa, name="mfa-verify"),
    path(
        "accounts/password-reset/",
        auth_views.PasswordResetView.as_view(),
        name="password_reset",
    ),
    path(
        "accounts/password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(),
        name="password_reset_done",
    ),
    path(
        "accounts/reset/<uidb64>/<token>/",
        SecurePasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "accounts/reset/done/",
        auth_views.PasswordResetCompleteView.as_view(),
        name="password_reset_complete",
    ),
    path("", dashboard, name="dashboard"),
    path("healthz/", healthz, name="healthz"),
    path("readyz/", readyz, name="readyz"),
    path("api/v1/analytics/", include("obe.analytics.urls")),
    path("evidence/", include("obe.evidence.urls")),
    path("catalog/", include("obe.curriculum.urls")),
    path("tasks/", include("obe.academic_lifecycle.urls")),
    path("me/progress/", my_progress, name="my_progress"),
]
