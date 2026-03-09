import os
import traceback
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
LOG_FILE = BASE_DIR / "logs" / "cpanel_debug_db.txt"
LOG_FILE.parent.mkdir(exist_ok=True)

def log(msg):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(str(msg) + "\n")

try:
    log("=== DEBUG DB BEGIN ===")

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

    import django
    django.setup()

    from django.db import connection

    log("Trying database connection...")
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        row = cursor.fetchone()
        log(f"Database query result: {row}")

    log("=== DEBUG DB OK ===")

except Exception:
    log("=== DEBUG DB ERROR ===")
    log(traceback.format_exc())
    raise