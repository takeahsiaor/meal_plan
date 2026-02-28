from django.core.management.base import BaseCommand

from meal_plan.models import Tag


DEFAULT_TAGS = [
    "Breakfast",
    "Lunch",
    "Dinner",
    "Ron",
    "Grill",
    "Main Course",
    "Vegetable",
    "Side",
    "Asian",
    "Rice",
    "Noodle",
    "Pasta",
    "Potato",
    "Sandwich",
    "Bread",
    "Dough",
    "Takeout",
    "Crockpot",
    "Beef",
    "Chicken",
    "Turkey",
    "Fish",
    "Shrimp",
    "Pork",
    "Sausage",
    "Fries"
]


class Command(BaseCommand):
    help = "Create default Tags from a built-in list of 5 names (idempotent)."

    def handle(self, *args, **options):
        created = 0
        for name in DEFAULT_TAGS:
            _, was_created = Tag.objects.get_or_create(name=name)
            if was_created:
                created += 1
        self.stdout.write(
            self.style.SUCCESS(f"Done. Tags created: {created} (total default: {len(DEFAULT_TAGS)})")
        )
