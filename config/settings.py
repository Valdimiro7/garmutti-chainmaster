from pathlib import Path
import os
from dotenv import load_dotenv
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parent.parent

# Carrega .env local, se existir
load_dotenv(BASE_DIR / ".env")

# =========================================================
# CORE
# =========================================================
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "django-insecure-change-me")
DEBUG = os.getenv("DJANGO_DEBUG", "False").strip().lower() in ("1", "true", "yes", "on")
ENV = os.getenv("DJANGO_ENV", "local").strip().lower()

# =========================================================
# HOSTS / CSRF
# =========================================================
allowed_hosts = os.getenv("DJANGO_ALLOWED_HOSTS", "")
ALLOWED_HOSTS = [h.strip() for h in allowed_hosts.split(",") if h.strip()]

if DEBUG and not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

csrf_origins = os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "")
CSRF_TRUSTED_ORIGINS = [o.strip() for o in csrf_origins.split(",") if o.strip()]

# =========================================================
# APPS
# =========================================================
INSTALLED_APPS = [
    "admin_material.apps.AdminMaterialDashboardConfig",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "widget_tweaks",
    "procurement",
]

# =========================================================
# AUTH / LOGIN / LOGOUT
# =========================================================
LOGIN_URL = "procurement:login"
LOGIN_REDIRECT_URL = "procurement:dashboard"
LOGOUT_REDIRECT_URL = "https://garmutti.co.mz/"

# =========================================================
# MIDDLEWARE
# =========================================================
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

# =========================================================
# TEMPLATES
# =========================================================
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
            ],
        },
    },
]

# =========================================================
# DATABASE
# =========================================================
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

if DATABASE_URL:
    parsed = urlparse(DATABASE_URL)

    if parsed.scheme.startswith("sqlite"):
        db_path = DATABASE_URL.replace("sqlite:///", "")
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": BASE_DIR / db_path,
            }
        }

    elif parsed.scheme in ["postgres", "postgresql"]:
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": parsed.path.lstrip("/"),
                "USER": parsed.username,
                "PASSWORD": parsed.password,
                "HOST": parsed.hostname,
                "PORT": parsed.port or 5432,
                "CONN_MAX_AGE": 60,
            }
        }

    elif parsed.scheme == "mysql":
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.mysql",
                "NAME": parsed.path.lstrip("/"),
                "USER": parsed.username,
                "PASSWORD": parsed.password,
                "HOST": parsed.hostname or "localhost",
                "PORT": parsed.port or 3306,
                "CONN_MAX_AGE": 60,
                "OPTIONS": {
                    "charset": "utf8mb4",
                    "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
                },
            }
        }

    else:
        raise ValueError(f"Unsupported database scheme: {parsed.scheme}")

else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# =========================================================
# PASSWORD VALIDATION
# =========================================================
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# =========================================================
# INTERNATIONALIZATION
# =========================================================
LANGUAGE_CODE = "en-us"
TIME_ZONE = os.getenv("DJANGO_TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True

# =========================================================
# STATIC / MEDIA
# =========================================================
STATIC_URL = os.getenv("DJANGO_STATIC_URL", "/static/")
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
}

# =========================================================
# SECURITY
# =========================================================
SECURE_SSL_REDIRECT = os.getenv("DJANGO_SECURE_SSL_REDIRECT", "False").lower() in ("1", "true", "yes", "on")
SESSION_COOKIE_SECURE = os.getenv("DJANGO_SESSION_COOKIE_SECURE", "False").lower() in ("1", "true", "yes", "on")
CSRF_COOKIE_SECURE = os.getenv("DJANGO_CSRF_COOKIE_SECURE", "False").lower() in ("1", "true", "yes", "on")

SECURE_HSTS_SECONDS = int(os.getenv("DJANGO_SECURE_HSTS_SECONDS", "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = os.getenv("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", "False").lower() in ("1", "true", "yes", "on")
SECURE_HSTS_PRELOAD = os.getenv("DJANGO_SECURE_HSTS_PRELOAD", "False").lower() in ("1", "true", "yes", "on")

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# =========================================================
# DEFAULT AUTO FIELD
# =========================================================
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# =========================================================
# LOGGING - FILE ONLY
# =========================================================
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

ERROR_LOG_FILE = LOG_DIR / "django_error.log"
SECURITY_LOG_FILE = LOG_DIR / "django_security.log"
DB_LOG_FILE = LOG_DIR / "django_db.log"
TEMPLATE_LOG_FILE = LOG_DIR / "django_template.log"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name}:{lineno} - {message}",
            "style": "{",
        },
    },
    "handlers": {
        "file_errors": {
            "class": "logging.FileHandler",
            "filename": str(ERROR_LOG_FILE),
            "formatter": "verbose",
            "level": "ERROR",
        },
        "file_security": {
            "class": "logging.FileHandler",
            "filename": str(SECURITY_LOG_FILE),
            "formatter": "verbose",
            "level": "WARNING",
        },
        "file_db": {
            "class": "logging.FileHandler",
            "filename": str(DB_LOG_FILE),
            "formatter": "verbose",
            "level": "ERROR",
        },
        "file_template": {
            "class": "logging.FileHandler",
            "filename": str(TEMPLATE_LOG_FILE),
            "formatter": "verbose",
            "level": "ERROR",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["file_errors"],
            "level": "ERROR",
            "propagate": True,
        },
        "django.request": {
            "handlers": ["file_errors"],
            "level": "ERROR",
            "propagate": False,
        },
        "django.server": {
            "handlers": ["file_errors"],
            "level": "ERROR",
            "propagate": False,
        },
        "django.security": {
            "handlers": ["file_security"],
            "level": "WARNING",
            "propagate": False,
        },
        "django.db.backends": {
            "handlers": ["file_db"],
            "level": "ERROR",
            "propagate": False,
        },
        "django.template": {
            "handlers": ["file_template"],
            "level": "ERROR",
            "propagate": False,
        },
    },
}