"""Root URL configuration for the OBE_System project.

Each module owns its own URLConf; the project wires them under a namespace.
For Task 1 only the presentation (`web`) module exposes routes (Home landing
page + Role_Switcher). Business-module workspaces are added in later tasks.
"""

from django.urls import include, path

urlpatterns = [
    path("", include("web.urls", namespace="web")),
]
