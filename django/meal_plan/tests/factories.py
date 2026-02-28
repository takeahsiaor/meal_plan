import factory
from django.utils import timezone

from meal_plan.models import (
    Ingredient,
    Plan,
    Recipe,
    RecipeIngredient,
    Store,
    StoreIngredient,
)


class IngredientFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Ingredient

    name = factory.Sequence(lambda n: f"ingredient-{n}")
    brand = None
    is_staple = False


class StoreFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Store

    name = factory.Sequence(lambda n: f"store-{n}")
    priority = factory.Sequence(lambda n: n)


class StoreIngredientFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = StoreIngredient

    store = factory.SubFactory(StoreFactory)
    ingredient = factory.SubFactory(IngredientFactory)
    is_preferred = False


class RecipeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Recipe

    name = factory.Sequence(lambda n: f"recipe-{n}")


class RecipeIngredientFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = RecipeIngredient

    recipe = factory.SubFactory(RecipeFactory)
    ingredient = factory.SubFactory(IngredientFactory)


class PlanFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Plan

    plan_date = factory.LazyFunction(lambda: timezone.now().date())
