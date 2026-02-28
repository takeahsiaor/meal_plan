import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from meal_plan.models import Ingredient, Store, StoreIngredient


class Command(BaseCommand):
    """JSON format:
    [
        {
            "name": str,
            "is_staple": bool,
            "stores": [str, str, ...],
            "preferred_store": str (optional)  # store name; StoreIngredient for this store gets is_preferred=True
        },
        ...
    ]
    """

    help = "Ingest ingredients from a JSON file and create Ingredient and store–ingredient links."

    def add_arguments(self, parser):
        parser.add_argument(
            "file",
            type=Path,
            help="Path to the JSON file (array of {name, is_stable, stores}).",
        )
        parser.add_argument(
            "--default-priority",
            type=int,
            default=0,
            help="Priority for stores created by this command (default: 0).",
        )

    def handle(self, *args, **options):
        path = options["file"]
        default_priority = options["default_priority"]

        if not path.exists():
            raise CommandError(f"File not found: {path}")

        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise CommandError(f"Invalid JSON: {e}") from e

        if not isinstance(data, list):
            raise CommandError("JSON root must be an array.")

        created_ingredients = 0

        store_cache = {}
        for i, item in enumerate(data):
            if not isinstance(item, dict):
                self.stderr.write(self.style.WARNING(f"Row {i}: skipping non-object {type(item).__name__}"))
                continue

            name = item.get("name")
            if not name or not isinstance(name, str):
                self.stderr.write(self.style.WARNING(f"Row {i}: missing or invalid 'name', skipping"))
                continue

            is_staple = item.get("is_staple", False)
            if not isinstance(is_staple, bool):
                is_staple = bool(is_staple)

            stores = item.get("stores")
            if not isinstance(stores, list):
                stores = []

            preferred_store = item.get("preferred_store")
            if preferred_store is not None and isinstance(preferred_store, str):
                preferred_store = preferred_store.strip().lower() or None
            else:
                preferred_store = None

            normalized_stores = {
                sn.strip().lower()
                for sn in stores
                if isinstance(sn, str) and sn.strip()
            }
            if preferred_store and preferred_store not in normalized_stores:
                self.stderr.write(
                    self.style.WARNING(
                        f"Row {i}: 'preferred_store' '{preferred_store}' not in 'stores', skipping"
                    )
                )
                continue

            ingredient, ing_created = Ingredient.objects.get_or_create(
                name=name.strip().lower(),
                defaults={"is_staple": is_staple},
            )
            if ing_created:
                created_ingredients += 1

            for store_name in stores:
                if not isinstance(store_name, str) or not store_name.strip():
                    continue

                store_name = store_name.strip().lower()
                if store_name not in store_cache:
                    store, _ = Store.objects.get_or_create(
                        name=store_name,
                        defaults={"priority": default_priority},
                    )
                    store_cache[store_name] = store
                else:
                    store = store_cache[store_name]

                StoreIngredient.objects.get_or_create(
                    store=store,
                    ingredient=ingredient,
                    defaults={"is_preferred": preferred_store == store_name if preferred_store else False},
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Ingredients created: {created_ingredients}"
            )
        )
