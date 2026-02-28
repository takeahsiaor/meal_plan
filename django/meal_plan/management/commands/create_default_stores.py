from django.core.management.base import BaseCommand

from meal_plan.models import Store


# (name, priority) — lower priority value = higher priority in ordering
DEFAULT_STORES = [
    ("meijer", 1),
    ("mitsuwa", 2),
    ("jewel", 3),
    ("costco", 3),
    ("international", 3),
    ("trader joes", 4),
    ("wildfork", 5),
    ("texas de brazil", 6)
]


class Command(BaseCommand):
    help = "Create default Stores from a built-in list (idempotent)."

    def handle(self, *args, **options):
        created = 0
        for name, priority in DEFAULT_STORES:
            _, was_created = Store.objects.get_or_create(
                name=name,
                defaults={"priority": priority},
            )
            if was_created:
                created += 1
        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Stores created: {created} (total default: {len(DEFAULT_STORES)})"
            )
        )
