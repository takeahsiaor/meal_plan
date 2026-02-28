import json
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from meal_plan.models import Ingredient, Recipe, RecipeIngredient, Tag


class Command(BaseCommand):
    """JSON format:
    [
        {
            "name": str,
            "ingredients": [str, str, ...],
            "tags": [str, str, ...],
            "last_used_on": "YYYY-MM-DD",
            "prep_notes": str (optional)
        },
        ...
    ]
    """

    help = "Ingest recipes from a JSON file and create Recipe and RecipeIngredient links."

    def add_arguments(self, parser):
        parser.add_argument(
            "file",
            type=Path,
            help="Path to the JSON file (array of {name, ingredients, tags, last_used_on}).",
        )

    def handle(self, *args, **options):
        path = options["file"]

        if not path.exists():
            raise CommandError(f"File not found: {path}")

        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise CommandError(f"Invalid JSON: {e}") from e

        if not isinstance(data, list):
            raise CommandError("JSON root must be an array.")

        tags_by_name = {t.name: t for t in Tag.objects.all()}
        ingredients_by_name = {i.name: i for i in Ingredient.objects.all()}

        created_recipes = 0
        links_added = 0
        skipped_existing = 0
        skipped_missing_refs = 0

        for i, item in enumerate(data):
            if not isinstance(item, dict):
                self.stderr.write(
                    self.style.WARNING(f"Row {i}: skipping non-object {type(item).__name__}")
                )
                continue

            name = item.get("name")
            if not name or not isinstance(name, str):
                self.stderr.write(self.style.WARNING(f"Row {i}: missing or invalid 'name', skipping"))
                continue

            name = name.strip()
            if Recipe.objects.filter(name=name).exists():
                self.stderr.write(
                    self.style.WARNING(f"Row {i}: recipe '{name}' already exists, skipping")
                )
                skipped_existing += 1
                continue

            tag_names_raw = item.get("tags")
            tag_names = []
            if isinstance(tag_names_raw, list):
                tag_names = [
                    t.strip() for t in tag_names_raw
                    if isinstance(t, str) and t.strip()
                ]
            missing_tags = [t for t in tag_names if t not in tags_by_name]
            if missing_tags:
                self.stderr.write(
                    self.style.WARNING(
                        f"Row {i} (recipe '{name}'): tags not found: {missing_tags}, skipping"
                    )
                )
                skipped_missing_refs += 1
                continue

            ingredients_raw = item.get("ingredients")
            ing_names = []
            if isinstance(ingredients_raw, list):
                ing_names = [
                    n.strip() for n in ingredients_raw
                    if isinstance(n, str) and n.strip()
                ]
            missing_ingredients = [n for n in ing_names if n not in ingredients_by_name]
            if missing_ingredients:
                self.stderr.write(
                    self.style.WARNING(
                        f"Row {i} (recipe '{name}'): ingredients not found: {missing_ingredients}, skipping"
                    )
                )
                skipped_missing_refs += 1
                continue

            last_used_on = item.get("last_used_on")
            last_used_date = None
            if last_used_on is not None and isinstance(last_used_on, str) and last_used_on.strip():
                try:
                    last_used_date = datetime.strptime(last_used_on.strip(), "%Y-%m-%d").date()
                except ValueError:
                    self.stderr.write(
                        self.style.WARNING(
                            f"Row {i} (recipe '{name}'): invalid 'last_used_on' "
                            f"'{last_used_on}' (expected YYYY-MM-DD), using null"
                        )
                    )

            prep_notes = item.get("prep_notes")
            if prep_notes is not None and not isinstance(prep_notes, str):
                prep_notes = str(prep_notes) if prep_notes else ""
            if prep_notes is None:
                prep_notes = ""

            recipe = Recipe.objects.create(
                name=name,
                last_used_on=last_used_date,
                prep_notes=prep_notes.strip() or None,
            )

            if tag_names:
                recipe.tags.set(tags_by_name[t] for t in tag_names)

            for ing_name in ing_names:
                ingredient = ingredients_by_name[ing_name]
                _, link_created = RecipeIngredient.objects.get_or_create(
                    recipe=recipe,
                    ingredient=ingredient,
                )
                if link_created:
                    links_added += 1

            created_recipes += 1

        parts = [
            f"Recipes created: {created_recipes}",
            f"recipe-ingredient links added: {links_added}",
        ]
        if skipped_existing:
            parts.append(f"skipped (already exists): {skipped_existing}")
        if skipped_missing_refs:
            parts.append(f"skipped (missing tags/ingredients): {skipped_missing_refs}")
        self.stdout.write(self.style.SUCCESS("Done. " + ", ".join(parts)))
