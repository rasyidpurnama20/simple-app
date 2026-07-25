"""
Django settings for the OBE_System project.

This is a development-only configuration (Requirement 15.4: no real
authentication / SSO / permission enforcement). Database connection settings
are read from environment variables so the same settings module works both
inside Docker Compose and on a developer machine, with defaults that match
docker-compose.yml.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


# --- Security / debug (development only) --------------------------------
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "dev-only-insecure-secret-key-not-for-production",
)
DEBUG = _env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = os.environ.get(
    "DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,0.0.0.0,web"
).split(",")

# CSRF trusted origins for local development.
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

# --- Applications -------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "django.contrib.messages",
    # OBE_System modules (each owns models / services / validators / dtos)
    "core",
    "timeline",
    "curriculum",
    "rps",
    "attainment",
    "injection",
    "web",
]

# Note: django.contrib.auth / sessions.contrib is intentionally replaced by a
# lightweight session-based Role_Switcher (no real authentication - Req 15.4).
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # In-app role/session context (swaps active DemoUser without auth).
    "core.middleware.RoleSwitcherMiddleware",
]

ROOT_URLCONF = "obe_system.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.messages.context_processors.messages",
                # Injects Dev_Banner + active role into every template.
                "core.context_processors.dev_context",
            ],
        },
    },
]

WSGI_APPLICATION = "obe_system.wsgi.application"

# --- Database (PostgreSQL 16) -------------------------------------------
# PostgreSQL is the default engine used by Docker Compose and production.
# For local test runs where PostgreSQL is unavailable, set
# DJANGO_DB_ENGINE=django.db.backends.sqlite3 to run against SQLite. This does
# not change the production/Docker configuration in any way.
_DB_ENGINE = os.environ.get("DJANGO_DB_ENGINE", "django.db.backends.postgresql")
if _DB_ENGINE == "django.db.backends.sqlite3":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": os.environ.get("SQLITE_PATH", str(BASE_DIR / "db.sqlite3")),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": _DB_ENGINE,
            "NAME": os.environ.get("POSTGRES_DB", "obe_system"),
            "USER": os.environ.get("POSTGRES_USER", "obe"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "obe_password"),
            "HOST": os.environ.get("POSTGRES_HOST", "db"),
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        }
    }

# --- Password validation ------------------------------------------------
# Intentionally empty: no real authentication in this development build.

# --- Internationalization -----------------------------------------------
LANGUAGE_CODE = "id"  # Bahasa Indonesia (human-friendly OBE terminology)
TIME_ZONE = "Asia/Jakarta"
USE_I18N = True
USE_TZ = True

# --- Static files -------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# --- Misc ---------------------------------------------------------------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Session engine uses the database (db-backed sessions for the Role_Switcher).
SESSION_ENGINE = "django.contrib.sessions.backends.db"
