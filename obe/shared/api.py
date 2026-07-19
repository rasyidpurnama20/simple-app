from rest_framework.views import exception_handler as drf_exception_handler

from obe.shared.redaction import redact


def exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is not None:
        response.data = redact(
            {
                "error": {
                    "code": getattr(exc, "default_code", "request_error"),
                    "detail": response.data,
                }
            }
        )
    return response
