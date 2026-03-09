import os
import traceback
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
LOG_FILE = BASE_DIR / "logs" / "cpanel_debug_template.txt"
LOG_FILE.parent.mkdir(exist_ok=True)

def log(msg):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(str(msg) + "\n")

try:
    log("=== DEBUG TEMPLATE BEGIN ===")

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    os.environ.setdefault(
        "DATABASE_URL",
        "mysql://garmutti_procurementadmin:cYgCYGss2n54rca@localhost/garmutti_procurement_db"
    )

    import django
    django.setup()

    from django.template.loader import get_template

    templates_to_test = [
        "auth/login.html",
        "layouts/pro_base-auth.html",
        "includes/pro_head.html",
        "includes/pro_scripts.html",
    ]

    for tpl in templates_to_test:
        try:
            get_template(tpl)
            log(f"OK: {tpl}")
        except Exception:
            log(f"ERROR loading template: {tpl}")
            log(traceback.format_exc())

    log("=== DEBUG TEMPLATE END ===")

except Exception:
    log("=== DEBUG TEMPLATE GLOBAL ERROR ===")
    log(traceback.format_exc())
    raise