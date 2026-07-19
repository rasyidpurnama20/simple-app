from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from obe.academic_lifecycle.views import my_progress
from obe.shared.views import dashboard, healthz, readyz

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/login/", auth_views.LoginView.as_view(), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", dashboard, name="dashboard"),
    path("healthz/", healthz, name="healthz"),
    path("readyz/", readyz, name="readyz"),
    path("api/v1/analytics/", include("obe.analytics.urls")),
    path("catalog/", include("obe.curriculum.urls")),
    path("tasks/", include("obe.academic_lifecycle.urls")),
    path("me/progress/", my_progress, name="my_progress"),
]
