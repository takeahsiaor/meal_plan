import uuid
from django.db import models
from django.db.models import Q


class Recipe(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    last_used_on = models.DateField(null=True, blank=True)
    tags = models.ManyToManyField("Tag", blank=True)
    ingredients = models.ManyToManyField(
        "Ingredient", through="RecipeIngredient", blank=True
    )
    prep_notes = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.name


class Tag(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class Plan(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plan_date = models.DateField()
    recipes = models.ManyToManyField(Recipe, blank=True)

    def __str__(self):
        return str(self.plan_date)


class Ingredient(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    brand = models.CharField(max_length=255, null=True, blank=True)
    is_staple = models.BooleanField(default=False)

    def __str__(self):
        return self.name


class RecipeIngredient(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, db_column="recipe_id")
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE, db_column="ingredient_id")

    class Meta:
        unique_together = [["recipe", "ingredient"]]

    def __str__(self):
        return f"{self.recipe.name} — {self.ingredient.name}"


class StoreIngredient(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    store = models.ForeignKey("Store", on_delete=models.CASCADE, db_column="store_id")
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE, db_column="ingredient_id")
    is_preferred = models.BooleanField(default=False)

    class Meta:
        unique_together = [["store", "ingredient"]]
        constraints = [
            models.UniqueConstraint(
                fields=["ingredient"],
                condition=Q(is_preferred=True),
                name="storeingredient_unique_preferred_per_ingredient",
            ),
        ]

    def __str__(self):
        return f"{self.store.name} — {self.ingredient.name}"


class Store(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    priority = models.IntegerField()
    ingredients = models.ManyToManyField(
        Ingredient, through="StoreIngredient", blank=True
    )

    class Meta:
        ordering = ["priority"]

    def __str__(self):
        return self.name
