# Configure Django before any app or model code is imported.
import os

# Signal that we're running under pytest so settings use an in-memory test DB.
os.environ["RUNNING_PYTEST"] = "1"
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "meal_planner.settings")

import django
django.setup()

# Create schema in the in-memory database (migrations run once per test process).
from django.core.management import call_command

call_command("migrate", "--run-syncdb", verbosity=0)
