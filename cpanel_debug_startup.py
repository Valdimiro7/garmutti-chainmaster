import os
import sys
import traceback
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
LOG_FILE = BASE_DIR / "logs" / "cpanel_debug_startup.txt"
LOG_FILE.parent.mkdir(exist_ok=True)

def log(msg):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(str(msg) + "\n")

try:
    log("=== DEBUG STARTUP BEGIN ===")
    log(f"Python executable: {sys.executable}")
    log(f"Python version: {sys.version}")
    log(f"BASE_DIR: {BASE_DIR}")

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    log("DJANGO_SETTINGS_MODULE set successfully")

    import django
    log(f"Django imported successfully: {django.get_version()}")

    django.setup()
    log("django.setup() executed successfully")

    from django.conf import settings
    log(f"DEBUG: {settings.DEBUG}")
    log(f"ALLOWED_HOSTS: {settings.ALLOWED_HOSTS}")
    log(f"DATABASES: {settings.DATABASES}")
    log(f"INSTALLED_APPS count: {len(settings.INSTALLED_APPS)}")

    from django.core.wsgi import get_wsgi_application
    application = get_wsgi_application()
    log("WSGI application loaded successfully")

    log("=== DEBUG STARTUP OK ===")

except Exception:
    log("=== DEBUG STARTUP ERROR ===")
    log(traceback.format_exc())
    raise