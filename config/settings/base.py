from pathlib import Path

import environ

from config.settings.runtime import requested_profile, secret_value, secret_values
from obe.shared.queueing import build_task_queues, task_annotations, task_routes
from obe.shared.redaction import register_sensitive_values

BASE_DIR = Path(__file__).resolve().parents[2]
env = environ.Env(
    OBE_DEBUG=(bool, False),
    OBE_AI_ENABLED=(bool, False),
    OBE_MAINTENANCE_MODE=(bool, False),
    EVIDENCE_ANTIVIRUS_REQUIRED=(bool, False),
    OBE_TELEMETRY_ENABLED=(bool, False),
)
_REQUESTED_PROFILE = requested_profile()
if _REQUESTED_PROFILE == "local":
    environ.Env.read_env(BASE_DIR / ".env")


SECRET_KEY = secret_value("OBE_SECRET_KEY", "unsafe-local-only")
SECRET_KEY_FALLBACKS = secret_values("OBE_SECRET_KEY_FALLBACKS")
OBE_ENV = requested_profile()
DEBUG = env.bool("OBE_DEBUG")
ALLOWED_HOSTS = env.list("OBE_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
TIME_ZONE = env("OBE_TIME_ZONE", default="Asia/Jakarta")
LANGUAGE_CODE = "id-id"
USE_I18N = True
USE_TZ = True

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "obe.shared",
    "obe.identity",
    "obe.curriculum",
    "obe.learning",
    "obe.assessment",
    "obe.evidence",
    "obe.analytics",
    "obe.quality",
    "obe.ai",
    "obe.secure_exam",
    "obe.academic_lifecycle",
    "obe.integration",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "obe.shared.middleware.MaintenanceModeMiddleware",
    "obe.shared.middleware.QueryBudgetMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "obe.shared.middleware.CorrelationIdMiddleware",
    "obe.shared.middleware.SecurityHeadersMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "obe.shared.context_processors.release_context",
            ],
        },
    }
]

DATABASES = {
    "default": env.db_url_config(
        secret_value("DATABASE_URL", f"sqlite:///{BASE_DIR / 'db.sqlite3'}")
    )
}
DATABASES["default"].update(
    {
        "CONN_MAX_AGE": env.int("OBE_DB_CONN_MAX_AGE", default=60),
        "CONN_HEALTH_CHECKS": True,
    }
)
if DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql":
    DATABASES["default"].setdefault("OPTIONS", {}).update(
        {
            "connect_timeout": env.int("OBE_DB_CONNECT_TIMEOUT", default=5),
            "application_name": env("OBE_DB_APPLICATION_NAME", default="obe-apps"),
        }
    )
CACHE_URL = env("CACHE_URL", default="locmemcache://obe-local")
CACHES = {"default": env.cache_url_config(CACHE_URL)}
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"
SESSION_COOKIE_AGE = env.int("OBE_SESSION_TTL_SECONDS", default=3_600)

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "login"

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
MEDIA_ROOT = BASE_DIR / "var" / "uploads"
EVIDENCE_ROOT = Path(env("EVIDENCE_ROOT", default=str(BASE_DIR / "var" / "evidence")))
EVIDENCE_OWNER_QUOTA_BYTES = env.int("EVIDENCE_OWNER_QUOTA_BYTES", default=512 * 1024 * 1024)
EVIDENCE_DOWNLOAD_TTL_SECONDS = env.int("EVIDENCE_DOWNLOAD_TTL_SECONDS", default=300)
EVIDENCE_ANTIVIRUS_REQUIRED = env.bool("EVIDENCE_ANTIVIRUS_REQUIRED")
CLAMAV_HOST = env("CLAMAV_HOST", default="clamav")
CLAMAV_PORT = env.int("CLAMAV_PORT", default=3310)

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_THROTTLE_RATES": {"user": "120/min", "anon": "10/min"},
    "EXCEPTION_HANDLER": "obe.shared.api.exception_handler",
}

CELERY_BROKER_URL = secret_value("CELERY_BROKER_URL", "memory://")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="cache+memory://")
CELERY_TASK_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_DEFAULT_QUEUE = "interactive"
CELERY_TASK_DEFAULT_EXCHANGE = "obe.tasks"
CELERY_TASK_DEFAULT_EXCHANGE_TYPE = "direct"
CELERY_TASK_DEFAULT_ROUTING_KEY = "interactive"
CELERY_TASK_QUEUES = build_task_queues()
CELERY_TASK_ROUTES = task_routes()
CELERY_TASK_ANNOTATIONS = task_annotations()
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BROKER_HEARTBEAT = 30
CELERY_TASK_PUBLISH_RETRY = True
CELERY_TASK_PUBLISH_RETRY_POLICY = {
    "max_retries": 3,
    "interval_start": 0,
    "interval_step": 0.5,
    "interval_max": 2,
}
CELERY_RESULT_EXPIRES = env.int("OBE_TASK_RESULT_TTL_SECONDS", default=3_600)
CELERY_TASK_TIME_LIMIT = 300
CELERY_TASK_SOFT_TIME_LIMIT = 270
CELERY_BEAT_SCHEDULE = {
    "publish-outbox": {"task": "obe.shared.tasks.publish_outbox", "schedule": 2.0},
    "reconcile-stale-work": {
        "task": "obe.shared.tasks.reconcile_stale_work",
        "schedule": 60.0,
    },
    "collect-operational-metrics": {
        "task": "obe.shared.tasks.collect_operational_metrics",
        "schedule": 60.0,
    },
    "schedule-task-reminders": {
        "task": "obe.academic_lifecycle.tasks.schedule_task_reminders",
        "schedule": 900.0,
    },
}

OBE_AI_ENABLED = env.bool("OBE_AI_ENABLED")
LITELLM_URL = env("LITELLM_URL", default="http://litellm:4000")
LITELLM_API_KEY = secret_value("LITELLM_API_KEY")
OBE_EXAM_SIGNING_KEY = secret_value("OBE_EXAM_SIGNING_KEY")
OBE_EXAM_SIGNING_KEY_FALLBACKS = secret_values("OBE_EXAM_SIGNING_KEY_FALLBACKS")
OBE_EXAM_SYNC_TOKEN = secret_value("OBE_EXAM_SYNC_TOKEN")
OBE_RELEASE = env("OBE_RELEASE", default="dev")
OBE_MAINTENANCE_MODE = env.bool("OBE_MAINTENANCE_MODE")
OBE_MAINTENANCE_FILE = env("OBE_MAINTENANCE_FILE", default="")
OBE_QUERY_BUDGET = env.int("OBE_QUERY_BUDGET", default=50)
OBE_SLOW_QUERY_MS = env.int("OBE_SLOW_QUERY_MS", default=250)
OBE_DB_CONNECTION_LIMIT = env.int("OBE_DB_CONNECTION_LIMIT", default=20)
OBE_BACKUP_SUCCESS_FILE = env("OBE_BACKUP_SUCCESS_FILE", default="")
OBE_TASK_PAYLOAD_LIMIT_BYTES = env.int("OBE_TASK_PAYLOAD_LIMIT_BYTES", default=262_144)
OBE_OUTBOX_MAX_ATTEMPTS = env.int("OBE_OUTBOX_MAX_ATTEMPTS", default=5)
OBE_TELEMETRY_ENABLED = env.bool("OBE_TELEMETRY_ENABLED")
OTEL_EXPORTER_OTLP_ENDPOINT = env(
    "OTEL_EXPORTER_OTLP_ENDPOINT", default="http://otel-collector:4318"
)
OTEL_SERVICE_NAME = env("OTEL_SERVICE_NAME", default="obe-apps")
OTEL_METRIC_EXPORT_INTERVAL_MS = env.int("OTEL_METRIC_EXPORT_INTERVAL_MS", default=15_000)

register_sensitive_values(
    [
        SECRET_KEY,
        *SECRET_KEY_FALLBACKS,
        LITELLM_API_KEY,
        OBE_EXAM_SIGNING_KEY,
        *OBE_EXAM_SIGNING_KEY_FALLBACKS,
        OBE_EXAM_SYNC_TOKEN,
        str(DATABASES["default"].get("PASSWORD", "")),
    ]
)

DEFAULT_EXCEPTION_REPORTER_FILTER = "obe.shared.redaction.OBEExceptionReporterFilter"
CELERY_TASK_SEND_SENT_EVENT = False
CELERY_WORKER_SEND_TASK_EVENTS = False
CELERY_TASK_EAGER_PROPAGATES = True

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "redact_secrets": {"()": "obe.shared.redaction.SecretRedactionFilter"},
        "correlation": {"()": "obe.shared.telemetry.CorrelationContextFilter"},
    },
    "formatters": {
        "json": {
            "()": "obe.shared.redaction.RedactingFormatter",
            "format": '{{"level":"{levelname}","time":"{asctime}","logger":"{name}","correlation_id":"{correlation_id}","message":"{message}"}}',
            "style": "{",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "filters": ["correlation", "redact_secrets"],
        }
    },
    "root": {"handlers": ["console"], "level": "INFO"},
}
