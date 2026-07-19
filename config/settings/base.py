from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parents[2]
env = environ.Env(
    OBE_DEBUG=(bool, False),
    OBE_AI_ENABLED=(bool, False),
)
environ.Env.read_env(BASE_DIR / ".env")


def secret_value(name: str, default: str = "") -> str:
    secret_file = env(f"{name}_FILE", default="")
    if secret_file:
        return Path(secret_file).read_text(encoding="utf-8").strip()
    return env(name, default=default)


SECRET_KEY = secret_value("OBE_SECRET_KEY", "unsafe-local-only")
OBE_ENV = env("OBE_ENV", default="production")
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
CACHES = {
    "default": env.cache("CACHE_URL", default="locmemcache://obe-local"),
}

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

CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="memory://")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="cache+memory://")
CELERY_TASK_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 300
CELERY_TASK_SOFT_TIME_LIMIT = 270
CELERY_BEAT_SCHEDULE = {
    "publish-outbox": {"task": "obe.shared.tasks.publish_outbox", "schedule": 10.0},
    "schedule-task-reminders": {
        "task": "obe.academic_lifecycle.tasks.schedule_task_reminders",
        "schedule": 900.0,
    },
}

OBE_AI_ENABLED = env.bool("OBE_AI_ENABLED")
LITELLM_URL = env("LITELLM_URL", default="http://litellm:4000")
LITELLM_API_KEY = secret_value("LITELLM_API_KEY")
OBE_EXAM_SIGNING_KEY = secret_value("OBE_EXAM_SIGNING_KEY")
OBE_RELEASE = env("OBE_RELEASE", default="dev")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "format": '{{"level":"{levelname}","time":"{asctime}","logger":"{name}","message":"{message}"}}',
            "style": "{",
        }
    },
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "json"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
