import os
import traceback
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
LOG_FILE = BASE_DIR / "logs" / "cpanel_debug_request.txt"
LOG_FILE.parent.mkdir(exist_ok=True)

def log(msg):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(str(msg) + "\n")

try:
    log("=== DEBUG REQUEST BEGIN ===")

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    os.environ.setdefault(
        "DATABASE_URL",
        "mysql://garmutti_procurementadmin:cYgCYGss2n54rca@localhost/garmutti_procurement_db"
    )

    import django
    django.setup()

    from django.test import Client

    client = Client()

    urls_to_test = [
        "/login/",
        "/admin/",
        "/",
    ]

    for url in urls_to_test:
        log(f"\n--- Testing URL: {url} ---")
        try:
            response = client.get(
                url,
                HTTP_HOST="app.garmutti.co.mz",
                secure=True
            )
            log(f"Status code: {response.status_code}")
            content_preview = response.content[:1000].decode("utf-8", errors="ignore")
            log("Content preview:")
            log(content_preview)
        except Exception:
            log(f"ERROR while requesting {url}")
            log(traceback.format_exc())

    log("=== DEBUG REQUEST END ===")

except Exception:
    log("=== DEBUG REQUEST GLOBAL ERROR ===")
    log(traceback.format_exc())
    raise