from django.conf import settings


def release_context(_request):
    return {"obe_release": settings.OBE_RELEASE, "ai_enabled": settings.OBE_AI_ENABLED}
