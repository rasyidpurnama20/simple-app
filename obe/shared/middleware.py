import uuid


class CorrelationIdMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        raw = request.headers.get("X-Correlation-ID")
        try:
            request.correlation_id = uuid.UUID(raw) if raw else uuid.uuid4()
        except ValueError:
            request.correlation_id = uuid.uuid4()
        response = self.get_response(request)
        response["X-Correlation-ID"] = str(request.correlation_id)
        return response


class SecurityHeadersMiddleware:
    POLICY = (
        "default-src 'self'; img-src 'self' data:; font-src 'self'; "
        "style-src 'self'; script-src 'self'; connect-src 'self'; "
        "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault("Content-Security-Policy", self.POLICY)
        response.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        return response
