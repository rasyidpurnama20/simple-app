import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

from django.conf import settings

from obe.identity.services import can
from obe.shared.feature_flags import FlagContext, kill_switch_allows
from obe.shared.telemetry import record_ai, set_operational_gauge, span


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
    *,
    model_alias: str,
    messages: list[dict],
    data_class: str,
    timeout: int = 20,
    principal=None,
    scope_type: str = "global",
    scope_id: str = "*",
) -> GatewayResult:
    started = time.monotonic()
    if not settings.OBE_AI_ENABLED:
        record_ai(model_alias=model_alias, tokens=0, outcome="disabled", duration=0)
        raise AIDisabled("Fitur AI sedang dinonaktifkan; alur akademik tetap tersedia")
    if not kill_switch_allows("ai", context=FlagContext(environment=settings.OBE_ENV)):
        raise AIDisabled("Kill switch AI sedang aktif")
    if principal is not None and not can(
        principal, "ai.use", scope_type=scope_type, scope_id=scope_id
    ):
        raise PermissionError("Principal tidak memiliki izin AI pada scope ini")
    if data_class in {"restricted-exam", "personal"} and model_alias == "external-approved":
        record_ai(model_alias=model_alias, tokens=0, outcome="policy_denied", duration=0)
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
    with span("obe.ai.complete", {"model.alias": model_alias}):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
                result = json.loads(response.read())
        except (urllib.error.URLError, TimeoutError) as exc:
            set_operational_gauge("ai_circuit", 1, outcome="open")
            record_ai(
                model_alias=model_alias,
                tokens=0,
                outcome="unavailable",
                duration=time.monotonic() - started,
            )
            raise AIUnavailable("Gateway AI tidak tersedia; gunakan mode rules-only") from exc
        usage = result.get("usage", {})
        record_ai(
            model_alias=model_alias,
            tokens=int(usage.get("total_tokens", 0)),
            outcome="success",
            duration=time.monotonic() - started,
        )
        set_operational_gauge("ai_circuit", 0, outcome="closed")
        return GatewayResult(
            content=result["choices"][0]["message"]["content"],
            model=result.get("model", model_alias),
            usage=usage,
        )
