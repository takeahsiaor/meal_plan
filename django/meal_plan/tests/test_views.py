"""
Tests for shopping list logic in _build_plan_shopping_list and plan_delete.

Uses store priority as the main driver; is_preferred breaks ties when
we're already forced to use a lower-priority store for another ingredient.
"""
import json
import uuid
from datetime import date

import pytest
from django.urls import reverse

from meal_plan.models import Plan, PlanShoppingList
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


# --- validate_ingredient_store tests ---

@pytest.mark.django_db
def test_validate_ingredient_store_ingredient_id_and_store_match_returns_valid_true(client):
    """When StoreIngredient exists for store/ingredient, returns valid true."""
    store = StoreFactory(name="meijer")
    ing = IngredientFactory(name="carrot")
    StoreIngredientFactory(store=store, ingredient=ing, is_preferred=False)
    response = client.post(
        reverse("meal_plan:validate_ingredient_store"),
        data='{"store_id": "' + str(store.id) + '", "ingredient_id": "' + str(ing.id) + '"}',
        content_type="application/json",
    )
    assert response.status_code == 200
    assert response.json()["valid"] is True


@pytest.mark.django_db
def test_validate_ingredient_store_ingredient_id_and_store_no_match_returns_valid_false(client):
    """When StoreIngredient does not exist for store/ingredient, returns valid false."""
    store = StoreFactory(name="meijer")
    ing = IngredientFactory(name="carrot")
    # No StoreIngredient linking them
    response = client.post(
        reverse("meal_plan:validate_ingredient_store"),
        data='{"store_id": "' + str(store.id) + '", "ingredient_id": "' + str(ing.id) + '"}',
        content_type="application/json",
    )
    assert response.status_code == 200
    assert response.json()["valid"] is False


@pytest.mark.django_db
def test_validate_ingredient_store_ingredient_name_and_store_match_returns_valid_true(client):
    """When using ingredient_name and StoreIngredient exists, returns valid true."""
    store = StoreFactory(name="kroger")
    ing = IngredientFactory(name="bok choy")
    StoreIngredientFactory(store=store, ingredient=ing, is_preferred=False)
    response = client.post(
        reverse("meal_plan:validate_ingredient_store"),
        data='{"store_id": "' + str(store.id) + '", "ingredient_name": "bok choy"}',
        content_type="application/json",
    )
    assert response.status_code == 200
    assert response.json()["valid"] is True


@pytest.mark.django_db
def test_validate_ingredient_store_ingredient_name_not_found_returns_valid_false(client):
    """When ingredient_name does not match any Ingredient, returns valid false."""
    store = StoreFactory(name="meijer")
    response = client.post(
        reverse("meal_plan:validate_ingredient_store"),
        data='{"store_id": "' + str(store.id) + '", "ingredient_name": "nonexistent"}',
        content_type="application/json",
    )
    assert response.status_code == 200
    assert response.json()["valid"] is False


@pytest.mark.django_db
def test_validate_ingredient_store_invalid_ingredient_id_returns_valid_false(client):
    """When ingredient_id is not a valid/existing Ingredient, returns valid false."""
    store = StoreFactory(name="meijer")
    response = client.post(
        reverse("meal_plan:validate_ingredient_store"),
        data='{"store_id": "' + str(store.id) + '", "ingredient_id": "00000000-0000-0000-0000-000000000000"}',
        content_type="application/json",
    )
    assert response.status_code == 200
    assert response.json()["valid"] is False


@pytest.mark.django_db
def test_validate_ingredient_store_invalid_store_id_returns_valid_false(client):
    """When store_id does not exist, returns valid false."""
    ing = IngredientFactory(name="carrot")
    response = client.post(
        reverse("meal_plan:validate_ingredient_store"),
        data='{"store_id": "00000000-0000-0000-0000-000000000000", "ingredient_id": "' + str(ing.id) + '"}',
        content_type="application/json",
    )
    assert response.status_code == 200
    assert response.json()["valid"] is False


@pytest.mark.django_db
def test_validate_ingredient_store_no_ingredient_returns_400(client):
    """When neither ingredient_id nor ingredient_name provided (and store is not Other), returns 400."""
    store = StoreFactory(name="meijer")
    response = client.post(
        reverse("meal_plan:validate_ingredient_store"),
        data='{"store_id": "' + str(store.id) + '"}',
        content_type="application/json",
    )
    assert response.status_code == 400
    assert response.json()["valid"] is False


@pytest.mark.django_db
def test_validate_ingredient_store_invalid_json_returns_400(client):
    """POST with invalid JSON body returns 400."""
    response = client.post(
        reverse("meal_plan:validate_ingredient_store"),
        data="not json",
        content_type="application/json",
    )
    assert response.status_code == 400
    assert response.json()["valid"] is False


@pytest.mark.django_db
def test_validate_ingredient_store_ingredient_id_preferred_over_name(client):
    """When both ingredient_id and ingredient_name are sent, ingredient_id is used."""
    store = StoreFactory(name="meijer")
    ing = IngredientFactory(name="carrot")
    StoreIngredientFactory(store=store, ingredient=ing, is_preferred=False)
    other_ing = IngredientFactory(name="other")
    # ingredient_id points to ing (in store), ingredient_name would match "other" - id wins
    response = client.post(
        reverse("meal_plan:validate_ingredient_store"),
        data='{"store_id": "' + str(store.id) + '", "ingredient_id": "' + str(ing.id) + '", "ingredient_name": "other"}',
        content_type="application/json",
    )
    assert response.status_code == 200
    assert response.json()["valid"] is True


# --- plan_update_shopping_list tests ---


@pytest.mark.django_db
def test_plan_update_shopping_list_post_creates_and_persists_list(client):
    """POST with valid list_items creates PlanShoppingList and returns ok."""
    plan = PlanFactory()
    store = StoreFactory()
    ing = IngredientFactory(name="carrot")
    payload = {
        "list_items": {
            str(store.id): {
                "ingredients": [
                    {"name": "carrot", "recipes": ["Soup"], "is_staple": False, "ingredient_id": str(ing.id)},
                ],
                "is_manual": False,
            },
        }
    }
    response = client.post(
        reverse("meal_plan:plan_update_shopping_list", kwargs={"plan_id": plan.id}),
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    plan.refresh_from_db()
    shopping_list = plan.shopping_list
    assert list(shopping_list.list_items.keys()) == [str(store.id)]
    store_data = shopping_list.list_items[str(store.id)]
    assert store_data["is_manual"] is False
    assert len(store_data["ingredients"]) == 1
    item = store_data["ingredients"][0]
    assert item["name"] == "carrot"
    assert item["recipes"] == ["Soup"]
    assert item["is_staple"] is False
    assert item["ingredient_id"] == str(ing.id)


@pytest.mark.django_db
def test_plan_update_shopping_list_post_updates_existing_list(client):
    """POST updates existing PlanShoppingList list_items."""
    plan = PlanFactory()
    store = StoreFactory()
    PlanShoppingList.objects.create(plan=plan, list_items={"old-store": {"ingredients": [{"name": "old", "recipes": [], "is_staple": False}], "is_manual": False}})
    payload = {
        "list_items": {
            str(store.id): {"ingredients": [{"name": "carrot", "recipes": [], "is_staple": False}], "is_manual": False},
        }
    }
    response = client.post(
        reverse("meal_plan:plan_update_shopping_list", kwargs={"plan_id": plan.id}),
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert response.status_code == 200
    plan.refresh_from_db()
    assert plan.shopping_list.list_items == {str(store.id): {"ingredients": [{"name": "carrot", "recipes": [], "is_staple": False}], "is_manual": False}}


@pytest.mark.django_db
def test_plan_update_shopping_list_get_returns_405(client):
    """GET returns 405 Method not allowed."""
    plan = PlanFactory()
    response = client.get(reverse("meal_plan:plan_update_shopping_list", kwargs={"plan_id": plan.id}))
    assert response.status_code == 405
    assert response.json()["error"] == "Method not allowed"


@pytest.mark.django_db
def test_plan_update_shopping_list_invalid_json_returns_400(client):
    """POST with invalid JSON body returns 400."""
    plan = PlanFactory()
    response = client.post(
        reverse("meal_plan:plan_update_shopping_list", kwargs={"plan_id": plan.id}),
        data="not json",
        content_type="application/json",
    )
    assert response.status_code == 400
    assert response.json()["error"] == "Invalid JSON"


@pytest.mark.django_db
def test_plan_update_shopping_list_missing_list_items_returns_400(client):
    """POST without list_items returns 400."""
    plan = PlanFactory()
    response = client.post(
        reverse("meal_plan:plan_update_shopping_list", kwargs={"plan_id": plan.id}),
        data="{}",
        content_type="application/json",
    )
    assert response.status_code == 400
    assert response.json()["error"] == "list_items must be an object"


@pytest.mark.django_db
def test_plan_update_shopping_list_list_items_not_object_returns_400(client):
    """POST with list_items as non-object returns 400."""
    plan = PlanFactory()
    response = client.post(
        reverse("meal_plan:plan_update_shopping_list", kwargs={"plan_id": plan.id}),
        data='{"list_items": []}',
        content_type="application/json",
    )
    assert response.status_code == 400
    assert response.json()["error"] == "list_items must be an object"


@pytest.mark.django_db
def test_plan_update_shopping_list_plan_not_found_returns_404(client):
    """POST with nonexistent plan_id returns 404."""
    response = client.post(
        reverse("meal_plan:plan_update_shopping_list", kwargs={"plan_id": uuid.uuid4()}),
        data='{"list_items": {}}',
        content_type="application/json",
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_plan_update_shopping_list_normalizes_recipes_and_is_staple(client):
    """Recipes default to [], is_staple to False; invalid recipe entries filtered out."""
    plan = PlanFactory()
    store = StoreFactory()
    payload = {
        "list_items": {
            str(store.id): {
                "ingredients": [{"name": "carrot", "recipes": ["A", 1, "B"], "is_staple": True}],
                "is_manual": False,
            },
        }
    }
    response = client.post(
        reverse("meal_plan:plan_update_shopping_list", kwargs={"plan_id": plan.id}),
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert response.status_code == 200
    plan.refresh_from_db()
    item = plan.shopping_list.list_items[str(store.id)]["ingredients"][0]
    assert item["recipes"] == ["A", "B"]
    assert item["is_staple"] is True


@pytest.mark.django_db
def test_plan_update_shopping_list_skips_invalid_entries(client):
    """Skips store keys whose value is not dict with ingredients or list; skips items without string name."""
    plan = PlanFactory()
    store = StoreFactory()
    payload = {
        "list_items": {
            str(store.id): {
                "ingredients": [
                    {"name": "carrot", "recipes": [], "is_staple": False},
                    {"recipes": ["Soup"]},  # no name - skipped
                    {"name": "broccoli", "recipes": [], "is_staple": False},
                ],
                "is_manual": True,
            },
            "another_key": "not a list",  # skipped (value not a list or dict with ingredients)
        }
    }
    response = client.post(
        reverse("meal_plan:plan_update_shopping_list", kwargs={"plan_id": plan.id}),
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert response.status_code == 200
    plan.refresh_from_db()
    assert set(plan.shopping_list.list_items.keys()) == {str(store.id)}
    store_data = plan.shopping_list.list_items[str(store.id)]
    assert store_data["is_manual"] is True
    assert len(store_data["ingredients"]) == 2
    names = [it["name"] for it in store_data["ingredients"]]
    assert names == ["carrot", "broccoli"]
