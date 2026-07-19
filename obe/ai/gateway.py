import json
import urllib.error
import urllib.request
from dataclasses import dataclass

from django.conf import settings


class AIDisabled(RuntimeError):
    pass


class AIUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class GatewayResult:
    content: str
    model: str
    usage: dict


def complete(
    *, model_alias: str, messages: list[dict], data_class: str, timeout: int = 20
) -> GatewayResult:
    if not settings.OBE_AI_ENABLED:
        raise AIDisabled("Fitur AI sedang dinonaktifkan; alur akademik tetap tersedia")
    if data_class in {"restricted-exam", "personal"} and model_alias == "external-approved":
        raise PermissionError("Data restricted/personal tidak boleh dikirim ke provider eksternal")
    payload = json.dumps({"model": model_alias, "messages": messages, "temperature": 0}).encode()
    request = urllib.request.Request(
        f"{settings.LITELLM_URL.rstrip('/')}/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {settings.LITELLM_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            result = json.loads(response.read())
    except (urllib.error.URLError, TimeoutError) as exc:
        raise AIUnavailable("Gateway AI tidak tersedia; gunakan mode rules-only") from exc
    return GatewayResult(
        content=result["choices"][0]["message"]["content"],
        model=result.get("model", model_alias),
        usage=result.get("usage", {}),
    )
