"""
Tests for shopping list logic in _build_plan_shopping_list and plan_delete.

Uses store priority as the main driver; is_preferred breaks ties when
we're already forced to use a lower-priority store for another ingredient.
"""
from datetime import date

import pytest
from django.urls import reverse

from meal_plan.models import Plan
from meal_plan.views import _build_plan_shopping_list

from .factories import (
    IngredientFactory,
    PlanFactory,
    RecipeFactory,
    RecipeIngredientFactory,
    StoreFactory,
    StoreIngredientFactory,
)


def _ingredients_by_store(result):
    """Return dict store_name -> set of ingredient names for assertions."""
    by_store = {}
    for store, items in result:
        name = store.name if store else "other"
        by_store[name] = {entry[0].name for entry in items}
    return by_store


@pytest.mark.django_db
def test_empty_plan_returns_empty_list():
    plan = PlanFactory()
    # No recipes added
    assert _build_plan_shopping_list(plan) == []


@pytest.mark.django_db
def test_plan_with_recipes_no_ingredients_returns_empty_list():
    plan = PlanFactory()
    recipe = RecipeFactory()
    plan.recipes.add(recipe)
    assert _build_plan_shopping_list(plan) == []


@pytest.mark.django_db
def test_single_ingredient_single_store_assigned_to_that_store():
    high = StoreFactory(name="meijer", priority=0)
    ing = IngredientFactory(name="carrot")
    StoreIngredientFactory(store=high, ingredient=ing, is_preferred=False)
    recipe = RecipeFactory(name="Soup")
    RecipeIngredientFactory(recipe=recipe, ingredient=ing)
    plan = PlanFactory()
    plan.recipes.add(recipe)

    result = _build_plan_shopping_list(plan)
    by_store = _ingredients_by_store(result)
    assert by_store == {"meijer": {"carrot"}}


@pytest.mark.django_db
def test_store_priority_drives_assignment_when_ingredient_at_multiple_stores():
    """Higher-priority store gets the ingredient when it's available at both."""
    meijer = StoreFactory(name="meijer", priority=0)
    international = StoreFactory(name="international", priority=1)
    ing = IngredientFactory(name="bok choy")
    StoreIngredientFactory(store=meijer, ingredient=ing, is_preferred=False)
    StoreIngredientFactory(store=international, ingredient=ing, is_preferred=False)
    recipe = RecipeFactory(name="Stir Fry")
    RecipeIngredientFactory(recipe=recipe, ingredient=ing)
    plan = PlanFactory()
    plan.recipes.add(recipe)

    result = _build_plan_shopping_list(plan)
    by_store = _ingredients_by_store(result)
    assert by_store == {"meijer": {"bok choy"}}


@pytest.mark.django_db
def test_forced_lower_priority_store_then_is_preferred_assigns_multi_store_ingredient():
    """
    Beef shank only at International; bok choy at Meijer and International.
    Bok choy preferred at International -> we assign bok choy to International
    since we're already going there.
    """
    meijer = StoreFactory(name="meijer", priority=0)
    international = StoreFactory(name="international", priority=1)
    beef_shank = IngredientFactory(name="beef shank")
    bok_choy = IngredientFactory(name="bok choy")
    apple = IngredientFactory(name="apple")
    StoreIngredientFactory(store=international, ingredient=beef_shank, is_preferred=True)
    StoreIngredientFactory(store=meijer, ingredient=bok_choy, is_preferred=False)
    StoreIngredientFactory(store=international, ingredient=bok_choy, is_preferred=True)
    StoreIngredientFactory(store=meijer, ingredient=apple, is_preferred=False)
    recipe = RecipeFactory(name="Stew")
    RecipeIngredientFactory(recipe=recipe, ingredient=beef_shank)
    RecipeIngredientFactory(recipe=recipe, ingredient=bok_choy)
    recipe2 = RecipeFactory(name="Apple Pie")
    RecipeIngredientFactory(recipe=recipe2, ingredient=apple)
    plan = PlanFactory()
    plan.recipes.add(recipe)
    plan.recipes.add(recipe2)

    result = _build_plan_shopping_list(plan)
    by_store = _ingredients_by_store(result)
    assert by_store["international"] == {"beef shank", "bok choy"}
    assert by_store["meijer"] == {"apple"}


@pytest.mark.django_db
def test_multi_store_ingredient_no_preferred_uses_store_already_used():
    """When we must use a lower-priority store for one ingredient, a multi-store
    ingredient with no preferred goes to the store we're already using (minimize stores).
    """
    meijer = StoreFactory(name="meijer", priority=0)
    international = StoreFactory(name="international", priority=1)
    only_at_international = IngredientFactory(name="beef shank")
    at_both = IngredientFactory(name="bok choy")
    StoreIngredientFactory(store=international, ingredient=only_at_international, is_preferred=True)
    StoreIngredientFactory(store=meijer, ingredient=at_both, is_preferred=False)
    StoreIngredientFactory(store=international, ingredient=at_both, is_preferred=False)
    recipe = RecipeFactory(name="Stew")
    RecipeIngredientFactory(recipe=recipe, ingredient=only_at_international)
    RecipeIngredientFactory(recipe=recipe, ingredient=at_both)
    plan = PlanFactory()
    plan.recipes.add(recipe)

    result = _build_plan_shopping_list(plan)
    by_store = _ingredients_by_store(result)
    # We're forced to International for beef shank. Bok choy has no preferred;
    # we prefer a store we're already using -> International.
    assert by_store["international"] == {"beef shank", "bok choy"}


@pytest.mark.django_db
def test_ingredient_in_no_store_appears_under_other():
    meijer = StoreFactory(name="meijer", priority=0)
    ing_in_store = IngredientFactory(name="carrot")
    ing_no_store = IngredientFactory(name="unicorn meat")
    StoreIngredientFactory(store=meijer, ingredient=ing_in_store, is_preferred=False)
    recipe = RecipeFactory(name="Salad")
    RecipeIngredientFactory(recipe=recipe, ingredient=ing_in_store)
    RecipeIngredientFactory(recipe=recipe, ingredient=ing_no_store)
    plan = PlanFactory()
    plan.recipes.add(recipe)

    result = _build_plan_shopping_list(plan)
    by_store = _ingredients_by_store(result)
    assert by_store["meijer"] == {"carrot"}
    assert by_store["other"] == {"unicorn meat"}


@pytest.mark.django_db
def test_is_preferred_ignored_when_preferred_store_not_used_otherwise():
    """If we don't need the lower-priority store for anything else, we don't add it;
    the multi-store ingredient goes to the higher-priority store even if preferred elsewhere.
    """
    meijer = StoreFactory(name="meijer", priority=0)
    international = StoreFactory(name="international", priority=1)
    bok_choy = IngredientFactory(name="bok choy")
    StoreIngredientFactory(store=meijer, ingredient=bok_choy, is_preferred=False)
    StoreIngredientFactory(store=international, ingredient=bok_choy, is_preferred=True)
    recipe = RecipeFactory(name="Stir Fry")
    RecipeIngredientFactory(recipe=recipe, ingredient=bok_choy)
    plan = PlanFactory()
    plan.recipes.add(recipe)

    result = _build_plan_shopping_list(plan)
    by_store = _ingredients_by_store(result)
    # We're not forced to International; minimize stores -> only Meijer.
    assert by_store == {"meijer": {"bok choy"}}


# --- plan_delete tests ---


@pytest.mark.django_db
def test_plan_delete_post_redirects_and_removes_plan(client):
    plan = PlanFactory(plan_date=date(2024, 6, 1))
    plan_id = plan.id
    response = client.post(reverse("meal_plan:plan_delete", kwargs={"plan_id": plan_id}))
    assert response.status_code == 302
    assert response.url == reverse("meal_plan:plan_list")
    assert not Plan.objects.filter(id=plan_id).exists()


@pytest.mark.django_db
def test_plan_delete_get_redirects_without_deleting(client):
    plan = PlanFactory(plan_date=date(2024, 6, 1))
    plan_id = plan.id
    response = client.get(reverse("meal_plan:plan_delete", kwargs={"plan_id": plan_id}))
    assert response.status_code == 302
    assert response.url == reverse("meal_plan:plan_list")
    assert Plan.objects.filter(id=plan_id).exists()


@pytest.mark.django_db
def test_plan_delete_sets_last_used_on_to_none_when_recipe_only_in_deleted_plan(client):
    recipe = RecipeFactory()
    plan = PlanFactory(plan_date=date(2024, 6, 1))
    plan.recipes.add(recipe)
    recipe.last_used_on = plan.plan_date
    recipe.save(update_fields=["last_used_on"])

    client.post(reverse("meal_plan:plan_delete", kwargs={"plan_id": plan.id}))

    recipe.refresh_from_db()
    assert recipe.last_used_on is None


@pytest.mark.django_db
def test_plan_delete_updates_last_used_on_to_latest_remaining_plan(client):
    recipe = RecipeFactory()
    older = PlanFactory(plan_date=date(2024, 1, 15))
    newer = PlanFactory(plan_date=date(2024, 6, 1))
    older.recipes.add(recipe)
    newer.recipes.add(recipe)
    recipe.last_used_on = newer.plan_date
    recipe.save(update_fields=["last_used_on"])

    client.post(reverse("meal_plan:plan_delete", kwargs={"plan_id": newer.id}))

    recipe.refresh_from_db()
    assert recipe.last_used_on == date(2024, 1, 15)


@pytest.mark.django_db
def test_plan_delete_updates_each_recipe_by_latest_remaining_plan(client):
    """Recipe A only in deleted plan -> None. Recipe B in deleted plan and older plan -> older date."""
    recipe_a = RecipeFactory()
    recipe_b = RecipeFactory()
    older = PlanFactory(plan_date=date(2024, 2, 1))
    deleted = PlanFactory(plan_date=date(2024, 5, 1))
    older.recipes.add(recipe_b)
    deleted.recipes.add(recipe_a, recipe_b)
    recipe_a.last_used_on = deleted.plan_date
    recipe_b.last_used_on = deleted.plan_date
    recipe_a.save(update_fields=["last_used_on"])
    recipe_b.save(update_fields=["last_used_on"])

    client.post(reverse("meal_plan:plan_delete", kwargs={"plan_id": deleted.id}))

    recipe_a.refresh_from_db()
    recipe_b.refresh_from_db()
    assert recipe_a.last_used_on is None
    assert recipe_b.last_used_on == date(2024, 2, 1)
