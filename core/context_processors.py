"""Template context processors for shared/dev context.

Injects the persistent Dev_Banner text (Requirement 15.3) and the active role
context + available role options (the Role_Switcher UI) into every template.
"""

from __future__ import annotations

from .services import RoleService

# Persistent development banner text (Requirement 15.3). Bahasa Indonesia to
# match the human-friendly OBE terminology used throughout the UI.
DEV_BANNER_TEXT = "DEVELOPMENT — BUKAN DATA RESMI"
DEV_BANNER_SUBTEXT = (
    "Lingkungan pengembangan dengan data sintetis. Tanpa autentikasi nyata."
)


def dev_context(request):
    """Provide Dev_Banner + Role_Switcher data to all templates."""
    role_context = getattr(request, "role_context", None)
    return {
        "dev_banner_text": DEV_BANNER_TEXT,
        "dev_banner_subtext": DEV_BANNER_SUBTEXT,
        "role_context": role_context,
        "available_roles": RoleService.available_roles(),
    }
