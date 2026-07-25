"""Thin presentation views for the Home landing page and Role_Switcher.

Views only parse input and call exactly one service method, then render a
template (Requirement 18.4). No business logic lives here.
"""

from __future__ import annotations

from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from core.exceptions import DomainError
from core.services import ACTIVE_DEMO_USER_SESSION_KEY

from .services import LandingService


def home(request):
    """Render the Home landing page for the active role."""
    landing = LandingService.landing(getattr(request, "role_context", None))
    return render(request, "web/home.html", {"landing": landing})


@require_POST
def switch_role(request):
    """Switch the active demo role (no authentication, Req 15.2/15.4)."""
    demo_user_id = request.POST.get("demo_user_id")
    try:
        context = LandingService.switch_role(int(demo_user_id or 0))
    except (DomainError, ValueError):
        messages.error(request, "Peran yang dipilih tidak tersedia.")
        return redirect("web:home")

    request.session[ACTIVE_DEMO_USER_SESSION_KEY] = context.demo_user_id
    messages.success(request, f"Sekarang melihat sebagai {context.role_label}.")
    return redirect("web:home")
