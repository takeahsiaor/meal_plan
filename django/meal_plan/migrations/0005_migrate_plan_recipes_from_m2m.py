# Data migration: copy plan-recipe links from old M2M table (meal_plan_plan_recipes)
# into PlanRecipe. Run after 0004 (PlanRecipe created) and before 0006 (Plan.recipes uses through).

from django.db import migrations


def copy_m2m_to_plan_recipe(apps, schema_editor):
    """Copy each (plan_id, recipe_id) from meal_plan_plan_recipes into PlanRecipe."""
    PlanRecipe = apps.get_model("meal_plan", "PlanRecipe")
    # Default Django M2M table name for Plan.recipes -> Recipe
    old_table = "meal_plan_plan_recipes"
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        # Skip if old table was already dropped (e.g. 0004 was applied before the split)
        cursor.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type='table' AND name=%s
            """,
            [old_table],
        )
        if not cursor.fetchone():
            return
        cursor.execute("SELECT plan_id, recipe_id FROM %s" % (old_table,))
        rows = cursor.fetchall()
    for plan_id, recipe_id in rows:
        PlanRecipe.objects.get_or_create(
            plan_id=plan_id,
            recipe_id=recipe_id,
            defaults={"notes": ""},
        )


def noop_reverse(apps, schema_editor):
    """No reverse: PlanRecipe rows are kept; old table is dropped in 0006."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("meal_plan", "0004_planrecipe_alter_plan_recipes"),
    ]

    operations = [
        migrations.RunPython(copy_m2m_to_plan_recipe, noop_reverse),
    ]
