import os
import django
from django.core.management import call_command

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

call_command("collectstatic", interactive=False, verbosity=2)
print("Collectstatic executed successfully.")