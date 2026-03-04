# Switch Plan.recipes to use PlanRecipe as the through model.
# Django cannot alter M2M to add through=; remove the old field then add the new one.
# This drops the old M2M table meal_plan_plan_recipes (data already in PlanRecipe).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("meal_plan", "0005_migrate_plan_recipes_from_m2m"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="plan",
            name="recipes",
        ),
        migrations.AddField(
            model_name="plan",
            name="recipes",
            field=models.ManyToManyField(
                blank=True, through="meal_plan.PlanRecipe", to="meal_plan.recipe"
            ),
        ),
    ]
