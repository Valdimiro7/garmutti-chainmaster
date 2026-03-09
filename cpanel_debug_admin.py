import os
import traceback
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
LOG_FILE = BASE_DIR / "logs" / "cpanel_debug_admin.txt"
LOG_FILE.parent.mkdir(exist_ok=True)

def log(msg):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(str(msg) + "\n")

try:
    log("=== DEBUG ADMIN BEGIN ===")

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    os.environ.setdefault(
        "DATABASE_URL",
        "mysql://garmutti_procurementadmin:cYgCYGss2n54rca@localhost/garmutti_procurement_db"
    )

    import django
    django.setup()

    from django.contrib import admin
    log("django admin imported successfully")

    from django.urls import reverse
    log(f"admin index url: {reverse('admin:index')}")

    log("=== DEBUG ADMIN OK ===")

except Exception:
    log("=== DEBUG ADMIN ERROR ===")
    log(traceback.format_exc())
    raise