"""Role_Switcher middleware.

Resolves the active ``DemoUser`` from the session on every request and attaches
it to ``request.demo_user`` / ``request.role_context``. This is the single
seam that swaps the active role WITHOUT any real authentication
(Requirement 15.4); a real auth backend can replace it later without changing
views or services.
"""

from __future__ import annotations

from django.utils.deprecation import MiddlewareMixin

from .services import ACTIVE_DEMO_USER_SESSION_KEY, RoleService


class RoleSwitcherMiddleware(MiddlewareMixin):
    """Attach the active demo-role context to each request."""

    def process_request(self, request):
        demo_user_id = request.session.get(ACTIVE_DEMO_USER_SESSION_KEY)

        # Fall back to a sensible default so the app is usable on first visit.
        if not demo_user_id:
            demo_user_id = RoleService.default_user_id()
            if demo_user_id:
                request.session[ACTIVE_DEMO_USER_SESSION_KEY] = demo_user_id

        request.role_context = RoleService.active_context(demo_user_id)
        request.demo_user_id = demo_user_id
