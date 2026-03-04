import json
import uuid
from datetime import datetime, timedelta
from urllib.parse import urlencode

from django.contrib import messages
from django.db.models import F
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.generic import ListView, View

from .forms import PlanDateForm
from .models import (
    Ingredient,
    Plan,
    PlanShoppingList,
    Recipe,
    Store,
    StoreIngredient,
    Tag,
)
from .schemas import ShoppingListItem, serialize_list_items


class PlanListView(ListView):
    model = Plan
    context_object_name = "plans"
    template_name = "meal_plan/plan_list.html"

    def get_queryset(self):
        qs = Plan.objects.prefetch_related("recipes").order_by("-plan_date")
        tab = self.request.GET.get("tab", "upcoming")
        today = timezone.localdate()
        if tab == "upcoming":
            qs = qs.filter(plan_date__gte=today)
        elif tab == "recent":
            cutoff = today - timedelta(days=90)
            qs = qs.filter(plan_date__lt=today, plan_date__gte=cutoff)
        # "all" = no extra filter
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_tab"] = self.request.GET.get("tab", "upcoming")
        return context


def _normalize_ingredient_ids(ingredient_ids_or_objects):
    """Convert mix of UUIDs, strings, and Ingredient instances to set of UUIDs and fetch Ingredient instances."""
    ids = set()
    for x in ingredient_ids_or_objects:
        if hasattr(x, "id"):
            ids.add(x.id)
        else:
            try:
                ids.add(uuid.UUID(str(x)))
            except (TypeError, ValueError):
                continue
    if not ids:
        return ids, {}
    ingredients = {ing.id: ing for ing in Ingredient.objects.filter(id__in=ids)}
    return ids, ingredients


def _build_shopping_list(ingredient_ids_or_objects, extra=None, must_visit_store_ids=None):
    """
    Build shopping list from a set of ingredients, grouped by store (minimize stores).

    ingredient_ids_or_objects: iterable of ingredient UUIDs or Ingredient model instances.
    extra: optional dict mapping ingredient_id (UUID) -> {"recipe_names": list[str], "is_staple": bool}.
          If missing for an ingredient, recipe_names=[], is_staple=ingredient.is_staple.
    must_visit_store_ids: optional set of store UUIDs that must appear in the result and be treated as
          already-used (ingredients will be assigned to them when possible, e.g. for manually added stores).

    Returns list of (store, items) where items is list of (ingredient, recipe_names, is_staple, color_class).
    """
    extra = extra or {}
    our_ingredient_ids, ingredients_by_id = _normalize_ingredient_ids(ingredient_ids_or_objects)
    if not our_ingredient_ids:
        return []

    # All stores by priority (lower priority value = higher priority)
    stores = list(Store.objects.prefetch_related("ingredients").order_by("priority"))
    store_ids_set = {s.id for s in stores}
    store_ingredient_ids = {s.id: set(s.ingredients.values_list("id", flat=True)) for s in stores}

    # Must-visit stores (e.g. manually added) are treated as already used so assignment prefers them
    used_stores = set()
    if must_visit_store_ids:
        used_stores = {sid for sid in must_visit_store_ids if sid in store_ids_set}

    # (ingredient_id, store_id) pairs where this store is the preferred source for this ingredient
    store_ids = [s.id for s in stores]
    preferred_pairs = set(
        StoreIngredient.objects.filter(
            ingredient_id__in=our_ingredient_ids,
            store_id__in=store_ids,
            is_preferred=True,
        ).values_list("ingredient_id", "store_id")
    )

    # For each store, count how many of our ingredients it has (for tie-break)
    def our_count(store_id):
        return len(our_ingredient_ids & store_ingredient_ids.get(store_id, set()))

    # For each ingredient, get list of (Store, our_count, is_preferred) that have it
    ing_to_stores = {}  # ingredient_id -> list of (Store, our_count, is_preferred)
    for ing_id in our_ingredient_ids:
        options = [
            (s, our_count(s.id), (ing_id, s.id) in preferred_pairs)
            for s in stores
            if ing_id in store_ingredient_ids.get(s.id, set())
        ]
        options.sort(key=lambda x: (x[0].priority, -x[2], -x[1]))
        ing_to_stores[ing_id] = options

    # Assign each ingredient to one store: single-store forces that store; else prefer store we're already using
    assigned = {}  # ingredient_id -> Store

    # First pass: ingredients with only one store
    for ing_id, options in ing_to_stores.items():
        if len(options) == 1:
            s = options[0][0]
            assigned[ing_id] = s
            used_stores.add(s.id)

    # Second pass: multi-store ingredients – prefer a store we're already using; among those, prefer is_preferred
    for ing_id, options in ing_to_stores.items():
        if ing_id in assigned:
            continue
        if not options:
            continue
        for s, _, is_preferred in options:
            if s.id in used_stores and is_preferred:
                assigned[ing_id] = s
                break
        else:
            for s, _, _ in options:
                if s.id in used_stores:
                    assigned[ing_id] = s
                    break
            else:
                s = options[0][0]
                assigned[ing_id] = s
                used_stores.add(s.id)

    # Ingredients in no store: assign to None (Other)
    for ing_id in our_ingredient_ids:
        if ing_id not in assigned:
            assigned[ing_id] = None

    # Build output by store: (store, [(ingredient, recipe_names, is_staple, color_class), ...])
    store_to_items = {}  # store_id or "other" -> (Store or None, list)
    for store in stores:
        if store.id in used_stores:
            store_to_items[store.id] = (store, [])
    store_to_items["other"] = (None, [])

    for ing_id in our_ingredient_ids:
        ing = ingredients_by_id.get(ing_id)
        if not ing:
            continue
        meta = extra.get(ing_id, {})
        recipe_names = sorted(meta.get("recipe_names", []))
        is_staple = meta.get("is_staple", ing.is_staple)
        color = "secondary"
        entry = (ing, recipe_names, is_staple, color)
        store = assigned[ing_id]
        if store is None:
            store_to_items["other"][1].append(entry)
        else:
            store_to_items[store.id][1].append(entry)

    result = []
    for store in stores:
        if store.id in store_to_items:
            items = store_to_items[store.id][1]
            result.append(
                (store_to_items[store.id][0], sorted(items, key=lambda x: ((x[1][0] if x[1] else ""), x[2], x[0].name)))
            )
    if store_to_items["other"][1]:
        result.append(
            (None, sorted(store_to_items["other"][1], key=lambda x: ((x[1][0] if x[1] else ""), x[2], x[0].name)))
        )
    return result


def _build_plan_shopping_list(plan):
    """
    Build shopping list for a plan: ingredients from plan recipes, grouped by store.
    Returns list of (store, items) where items is list of (ingredient, recipe_names, is_staple, color_class).
    """
    recipes = list(plan.recipes.prefetch_related("ingredients").order_by("name"))
    if not recipes:
        return []

    ing_to_recipes = {}  # ingredient_id -> (Ingredient, set of recipe names)
    for recipe in recipes:
        for ing in recipe.ingredients.all():
            if ing.id not in ing_to_recipes:
                ing_to_recipes[ing.id] = [ing, set()]
            ing_to_recipes[ing.id][1].add(recipe.name)

    ingredient_ids = list(ing_to_recipes.keys())
    extra = {
        ing_id: {"recipe_names": list(names), "is_staple": ing.is_staple}
        for ing_id, (ing, names) in ing_to_recipes.items()
    }
    return _build_shopping_list(ingredient_ids, extra=extra)


def _initialize_plan_shopping_list(plan):
    """
    Build the shopping list from plan recipes and persist it as PlanShoppingList.list_items JSON.
    Idempotent per plan: replaces any existing list.
    Top-level keys are store UUID (str) or "Other". Value is {"ingredients": [...], "is_manual": False}.
    """
    shopping_by_store = _build_plan_shopping_list(plan)
    store_to_data = {}
    for store, items in shopping_by_store:
        store_key = str(store.id) if store is not None else "Other"
        store_to_data[store_key] = {
            "ingredients": [
                ShoppingListItem(
                    name=ing.name,
                    recipes=tuple(sorted(recipe_names)),
                    is_staple=is_staple,
                    ingredient_id=str(ing.id),
                )
                for ing, recipe_names, is_staple, _color in items
            ],
            "is_manual": False,
        }
    shopping_list, _ = PlanShoppingList.objects.update_or_create(
        plan=plan, defaults={}
    )
    shopping_list.list_items = serialize_list_items(store_to_data)
    shopping_list.save(update_fields=["list_items"])


def plan_detail(request, plan_id):
    plan = get_object_or_404(
        Plan.objects.prefetch_related("recipes__ingredients"),
        id=plan_id,
    )
    try:
        shopping_list = plan.shopping_list
    except PlanShoppingList.DoesNotExist:
        _initialize_plan_shopping_list(plan)
        plan.refresh_from_db()
        shopping_list = plan.shopping_list
    recipes = list(plan.recipes.order_by("name"))
    available_recipes = Recipe.objects.exclude(
        id__in=plan.recipes.values_list("id", flat=True)
    ).order_by("name")
    list_items = shopping_list.list_items
    store_ids_in_list = [k for k in list_items.keys() if k != "Other"]
    available_stores = Store.objects.exclude(id__in=store_ids_in_list).order_by("priority")
    stores_by_id = {str(s.id): s for s in Store.objects.filter(id__in=store_ids_in_list)}
    shopping_list_display = []
    for store_key, value in list_items.items():
        if store_key == "Other":
            continue
        if isinstance(value, dict) and "ingredients" in value:
            items = value["ingredients"]
            is_manual = value.get("is_manual", False)
        else:
            items = value if isinstance(value, list) else []
            is_manual = False
        store = stores_by_id.get(store_key)
        display_name = store.name if store else store_key
        shopping_list_display.append((store_key, display_name, items, is_manual))
    all_ingredients = [{"id": str(i.id), "name": i.name} for i in Ingredient.objects.order_by("name")]
    tab_param = request.GET.get("tab", "shopping")
    active_tab = "recipes" if tab_param == "recipes" else "shopping"
    return render(
        request,
        "meal_plan/plan_detail.html",
        {
            "plan": plan,
            "recipes": recipes,
            "shopping_list_display": shopping_list_display,
            "active_tab": active_tab,
            "available_recipes": available_recipes,
            "available_stores": available_stores,
            "all_ingredients": all_ingredients,
            "plan_update_shopping_list_url": reverse("meal_plan:plan_update_shopping_list", kwargs={"plan_id": plan.id}),
            "validate_ingredient_store_url": reverse("meal_plan:validate_ingredient_store"),
        },
    )


def validate_ingredient_store(request):
    """
    GET or POST with store_id and ingredient_id (preferred) or ingredient_name.
    Returns JSON { "valid": true } if StoreIngredient exists for that store/ingredient; else { "valid": false }.
    """
    if request.method == "GET":
        store_id = request.GET.get("store_id")
        ingredient_id = request.GET.get("ingredient_id")
        ingredient_name = request.GET.get("ingredient_name")
    else:
        try:
            data = json.loads(request.body) if request.body else {}
        except (ValueError, TypeError):
            return JsonResponse({"valid": False}, status=400)
        store_id = data.get("store_id")
        ingredient_id = data.get("ingredient_id")
        ingredient_name = data.get("ingredient_name")
    if ingredient_id:
        try:
            ingredient = Ingredient.objects.get(id=ingredient_id)
        except (Ingredient.DoesNotExist, ValueError, TypeError):
            return JsonResponse({"valid": False})
    elif ingredient_name and isinstance(ingredient_name, str):
        ingredient = Ingredient.objects.filter(name=ingredient_name.strip()).first()
        if not ingredient:
            return JsonResponse({"valid": False})
    else:
        return JsonResponse({"valid": False}, status=400)
    try:
        store = Store.objects.get(id=store_id)
    except (Store.DoesNotExist, ValueError, TypeError):
        return JsonResponse({"valid": False})
    valid = StoreIngredient.objects.filter(store=store, ingredient=ingredient).exists()
    return JsonResponse({"valid": valid})


def plan_update_shopping_list(request, plan_id):
    """POST with JSON body { list_items: { "<store_id>": { "ingredients": [...], "is_manual": bool }, ... } } to persist list."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    plan = get_object_or_404(Plan, id=plan_id)
    try:
        data = json.loads(request.body)
    except (ValueError, TypeError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    list_items = data.get("list_items")
    if not isinstance(list_items, dict):
        return JsonResponse({"error": "list_items must be an object"}, status=400)
    normalized = {}
    for store_name, value in list_items.items():
        if not isinstance(store_name, str):
            continue
        if isinstance(value, dict) and "ingredients" in value:
            items = value.get("ingredients", [])
            is_manual = bool(value.get("is_manual", False))
        elif isinstance(value, list):
            items = value
            is_manual = False
        else:
            continue
        ingredient_rows = []
        for item in items:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            recipes = item.get("recipes")
            if not isinstance(name, str):
                continue
            if not isinstance(recipes, list):
                recipes = []
            recipes = [r for r in recipes if isinstance(r, str)]
            is_staple = bool(item.get("is_staple", False))
            row = {"name": name, "recipes": recipes, "is_staple": is_staple}
            if item.get("ingredient_id") and isinstance(item.get("ingredient_id"), str):
                row["ingredient_id"] = item["ingredient_id"]
            ingredient_rows.append(row)
        normalized[store_name] = {"ingredients": ingredient_rows, "is_manual": is_manual}
    shopping_list, _ = PlanShoppingList.objects.get_or_create(plan=plan, defaults={})
    shopping_list.list_items = normalized
    shopping_list.save(update_fields=["list_items"])
    return JsonResponse({"ok": True})


def plan_recalculate_stores(request, plan_id):
    """
    Recalculate minimum stores from current shopping list items (e.g. after user removes staples).
    POST only. Redirects back to plan detail.
    """
    if request.method != "POST":
        return redirect("meal_plan:plan_detail", plan_id=plan_id)
    plan = get_object_or_404(Plan, id=plan_id)
    try:
        shopping_list = plan.shopping_list
    except PlanShoppingList.DoesNotExist:
        messages.info(request, "No shopping list to recalculate.")
        return redirect("meal_plan:plan_detail", plan_id=plan_id)

    list_items = shopping_list.list_items or {}
    # Flatten: collect items with valid ingredient_id; collect manually added store IDs (must-visit)
    ingredient_ids = []
    extra = {}
    manual_store_keys = set()  # string keys for preserving is_manual in output

    for store_key, value in list_items.items():
        if store_key == "Other":
            continue
        if isinstance(value, dict) and "ingredients" in value:
            items = value["ingredients"]
            if value.get("is_manual"):
                manual_store_keys.add(store_key)
        elif isinstance(value, list):
            items = value
        else:
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            if not name or not isinstance(name, str):
                continue
            ing_id = item.get("ingredient_id") if isinstance(item.get("ingredient_id"), str) else None
            if not ing_id:
                continue
            try:
                parsed_id = uuid.UUID(ing_id)
            except (ValueError, TypeError):
                continue
            recipes = item.get("recipes")
            if not isinstance(recipes, list):
                recipes = []
            recipes = [r for r in recipes if isinstance(r, str)]
            is_staple = bool(item.get("is_staple", False))
            ingredient_ids.append(parsed_id)
            extra[parsed_id] = {"recipe_names": recipes, "is_staple": is_staple}

    # Resolve manual store keys to valid store UUIDs (must-visit stores)
    must_visit_store_ids = set()
    if manual_store_keys:
        try:
            parsed_manual = [uuid.UUID(k) for k in manual_store_keys]
            must_visit_store_ids = set(
                Store.objects.filter(id__in=parsed_manual).values_list("id", flat=True)
            )
        except (ValueError, TypeError):
            pass

    # Rebuild store assignment; manually added stores are must-visit and keep is_manual in output
    store_to_items = {}
    if ingredient_ids or must_visit_store_ids:
        shopping_by_store = _build_shopping_list(
            ingredient_ids, extra=extra, must_visit_store_ids=must_visit_store_ids
        )
        for store, items in shopping_by_store:
            if store is None:
                continue  # skip Other
            store_key = str(store.id)
            is_manual = store_key in manual_store_keys
            store_to_items[store_key] = {
                "ingredients": [
                    {
                        "name": ing.name,
                        "recipes": sorted(recipe_names),
                        "is_staple": is_staple,
                        "ingredient_id": str(ing.id),
                    }
                    for ing, recipe_names, is_staple, _ in items
                ],
                "is_manual": is_manual,
            }
        # When there are no ingredients, _build_shopping_list returns []; preserve manual stores with empty ingredients
        if not ingredient_ids and must_visit_store_ids:
            for store in Store.objects.filter(id__in=must_visit_store_ids):
                store_key = str(store.id)
                if store_key not in store_to_items:
                    store_to_items[store_key] = {"ingredients": [], "is_manual": True}

    shopping_list.list_items = store_to_items
    shopping_list.save(update_fields=["list_items"])
    messages.success(request, "Shopping list stores recalculated.")
    return redirect("meal_plan:plan_detail", plan_id=plan_id)


def plan_reset_shopping_list(request, plan_id):
    """
    Delete the plan's PlanShoppingList. On redirect to plan detail, initialization will run and recreate it from plan recipes.
    POST only. Redirects back to plan detail.
    """
    if request.method != "POST":
        return redirect("meal_plan:plan_detail", plan_id=plan_id)
    plan = get_object_or_404(Plan, id=plan_id)
    try:
        plan.shopping_list.delete()
        messages.success(request, "Shopping list reset to default.")
    except PlanShoppingList.DoesNotExist:
        messages.info(request, "Shopping list was already at default.")
    return redirect("meal_plan:plan_detail", plan_id=plan_id)


def plan_delete(request, plan_id):
    """Delete a plan. Only accepts POST. Updates last_used_on for each recipe in the plan."""
    if request.method != "POST":
        return redirect("meal_plan:plan_list")
    plan = get_object_or_404(Plan.objects.prefetch_related("recipes"), id=plan_id)
    plan_date_str = plan.plan_date.strftime("%b %d, %Y")

    # For each recipe in this plan, set last_used_on to the date of the latest other plan containing it, or None.
    for recipe in plan.recipes.all():
        last_plan = (
            Plan.objects.filter(recipes=recipe)
            .exclude(id=plan.id)
            .order_by("-plan_date")
            .first()
        )
        recipe.last_used_on = last_plan.plan_date if last_plan else None
        recipe.save(update_fields=["last_used_on"])

    plan.delete()
    messages.success(request, f"Plan for {plan_date_str} deleted.")
    return redirect("meal_plan:plan_list")


def plan_remove_recipe(request, plan_id, recipe_id):
    """Remove a recipe from a plan. POST only. Updates recipe last_used_on."""
    if request.method != "POST":
        return redirect("meal_plan:plan_detail", plan_id=plan_id)
    plan = get_object_or_404(Plan.objects.prefetch_related("recipes"), id=plan_id)
    recipe = get_object_or_404(Recipe, id=recipe_id)
    if not plan.recipes.filter(id=recipe_id).exists():
        messages.error(request, "Recipe is not in this plan.")
        return redirect("meal_plan:plan_detail", plan_id=plan_id)
    plan.recipes.remove(recipe)
    last_plan = (
        Plan.objects.filter(recipes=recipe)
        .order_by("-plan_date")
        .first()
    )
    recipe.last_used_on = last_plan.plan_date if last_plan else None
    recipe.save(update_fields=["last_used_on"])
    try:
        plan.shopping_list.delete()
    except PlanShoppingList.DoesNotExist:
        pass
    _initialize_plan_shopping_list(plan)
    messages.success(request, f"Removed {recipe.name} from the plan.")
    return redirect("meal_plan:plan_detail", plan_id=plan_id)


def plan_add_recipe(request, plan_id):
    """Add a recipe to a plan. POST with recipe_id. Redirects back to plan detail."""
    if request.method != "POST":
        return redirect("meal_plan:plan_detail", plan_id=plan_id)
    plan = get_object_or_404(Plan.objects.prefetch_related("recipes"), id=plan_id)
    recipe_id = request.POST.get("recipe_id")
    if not recipe_id:
        messages.error(request, "Please select a recipe.")
        return redirect("meal_plan:plan_detail", plan_id=plan_id)
    recipe = get_object_or_404(Recipe, id=recipe_id)
    if plan.recipes.filter(id=recipe_id).exists():
        messages.info(request, f"{recipe.name} is already in this plan.")
        return redirect("meal_plan:plan_detail", plan_id=plan_id)
    plan.recipes.add(recipe)
    if recipe.last_used_on is None or plan.plan_date > recipe.last_used_on:
        recipe.last_used_on = plan.plan_date
        recipe.save(update_fields=["last_used_on"])
    try:
        plan.shopping_list.delete()
    except PlanShoppingList.DoesNotExist:
        pass
    _initialize_plan_shopping_list(plan)
    messages.success(request, f"Added {recipe.name} to the plan.")
    return redirect("meal_plan:plan_detail", plan_id=plan_id)


CART_SESSION_KEY = "recipe_cart"


def get_cart_recipe_ids(request):
    """Return set of recipe IDs (str) currently in the cart."""
    cart = request.session.get(CART_SESSION_KEY, [])
    return set(str(x) for x in cart)


def add_to_cart(request, recipe_id):
    cart = request.session.get(CART_SESSION_KEY, [])
    rid = str(recipe_id)
    if rid not in cart:
        cart.append(rid)
        request.session[CART_SESSION_KEY] = cart
        request.session.modified = True
    next_url = request.GET.get("next") or request.POST.get("next") or reverse("meal_plan:recipe_list")
    return HttpResponseRedirect(next_url)


def remove_from_cart(request, recipe_id):
    cart = request.session.get(CART_SESSION_KEY, [])
    rid = str(recipe_id)
    if rid in cart:
        cart = [x for x in cart if x != rid]
        request.session[CART_SESSION_KEY] = cart
        request.session.modified = True
    next_url = request.GET.get("next") or request.POST.get("next") or reverse("meal_plan:recipe_list")
    return HttpResponseRedirect(next_url)


class RecipeListView(ListView):
    model = Recipe
    context_object_name = "recipes"
    template_name = "meal_plan/recipe_list.html"

    def get_queryset(self):
        qs = (
            Recipe.objects.prefetch_related("tags")
            .order_by(F("last_used_on").asc(nulls_first=True))
        )
        selected_tags = self.request.GET.getlist("tag")
        tag_mode = (self.request.GET.get("tag_mode") or "any").lower()
        if selected_tags:
            if tag_mode == "all":
                for tag in selected_tags:
                    qs = qs.filter(tags__name=tag)
                qs = qs.distinct()
            else:
                qs = qs.filter(tags__name__in=selected_tags).distinct()
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tags = list(Tag.objects.order_by("name"))
        selected_tags = self.request.GET.getlist("tag")
        tag_mode = (self.request.GET.get("tag_mode") or "any").lower()
        base_url = reverse("meal_plan:recipe_list")

        def query_string(tags_list, mode=None):
            if not tags_list and mode is None:
                return base_url
            params = [("tag", t) for t in tags_list]
            if mode and (tags_list or mode != "any"):
                params.append(("tag_mode", mode))
            return f"{base_url}?{urlencode(params, doseq=True)}" if params else base_url

        pills = []
        # "All" pill (no tag filter)
        pills.append({
            "name": "All",
            "is_selected": len(selected_tags) == 0,
            "url": base_url,
        })
        # One pill per tag (toggle: add or remove this tag from filter)
        for tag in tags:
            if tag.name in selected_tags:
                new_tags = [t for t in selected_tags if t != tag.name]
                url = query_string(new_tags, tag_mode if new_tags else None)
            else:
                new_tags = selected_tags + [tag.name]
                url = query_string(new_tags, tag_mode)
            pills.append({
                "name": tag.name,
                "is_selected": tag.name in selected_tags,
                "url": url,
            })

        context["tag_mode"] = tag_mode
        context["has_tag_filter"] = len(selected_tags) > 0
        context["tag_mode_any_url"] = query_string(selected_tags, "any") if selected_tags else base_url
        context["tag_mode_all_url"] = query_string(selected_tags, "all") if selected_tags else base_url

        context["tag_pills"] = pills
        context["cart_recipe_ids"] = get_cart_recipe_ids(self.request)
        cart = self.request.session.get(CART_SESSION_KEY, [])
        context["cart_count"] = len(cart)
        cart_recipes = list(Recipe.objects.filter(id__in=cart).prefetch_related("tags").order_by("name")) if cart else []
        context["cart_recipes"] = cart_recipes
        # Tag counts across cart: tag name -> number of cart recipes that have that tag
        tag_counts = {}
        for recipe in cart_recipes:
            for tag in recipe.tags.all():
                tag_counts[tag.name] = tag_counts.get(tag.name, 0) + 1
        context["cart_tag_counts"] = sorted(tag_counts.items(), key=lambda x: x[0])
        context["plan_form"] = PlanDateForm(initial={"plan_date": timezone.localdate()})
        context["current_url"] = self.request.get_full_path()
        return context


class CartView(View):
    """POST creates plan and clears cart. GET redirects to recipe list (cart is in sidebar there)."""

    def get(self, request):
        return redirect("meal_plan:recipe_list")

    def post(self, request):
        form = PlanDateForm(request.POST)
        cart = request.session.get(CART_SESSION_KEY, [])
        if not cart:
            return redirect("meal_plan:recipe_list")
        recipes = Recipe.objects.filter(id__in=cart)
        if not form.is_valid():
            messages.error(request, "Please enter a valid plan date.")
            return redirect(request.POST.get("next") or request.GET.get("next") or reverse("meal_plan:recipe_list"))
        plan_date = form.cleaned_data["plan_date"]
        plan = Plan.objects.create(plan_date=plan_date)
        plan.recipes.set(recipes)
        _initialize_plan_shopping_list(plan)
        Recipe.objects.filter(id__in=cart).update(last_used_on=plan_date)
        request.session.pop(CART_SESSION_KEY, None)
        request.session.modified = True
        return redirect("meal_plan:plan_detail", plan_id=plan.id)


def recipe_detail_json(request, recipe_id):
    """Return recipe details as JSON for the recipe modal."""
    recipe = get_object_or_404(
        Recipe.objects.prefetch_related("tags", "ingredients"),
        id=recipe_id,
    )
    last_used = None
    if recipe.last_used_on:
        last_used = recipe.last_used_on.strftime("%b %d, %Y")
    recent_plans = []
    for p in Plan.objects.filter(recipes=recipe).prefetch_related("recipes").order_by("-plan_date")[:5]:
        recent_plans.append({
            "plan_id": str(p.id),
            "plan_date": p.plan_date.strftime("%b %d, %Y"),
            "recipes_used": sorted(r.name for r in p.recipes.all()),
        })
    return JsonResponse({
        "name": recipe.name,
        "last_used_on": last_used,
        "tags": [t.name for t in recipe.tags.all()],
        "ingredients": [i.name for i in recipe.ingredients.order_by("name")],
        "recent_plans": recent_plans,
    })


def add_to_cart_view(request, recipe_id):
    get_object_or_404(Recipe, id=recipe_id)
    return add_to_cart(request, recipe_id)


def remove_from_cart_view(request, recipe_id):
    get_object_or_404(Recipe, id=recipe_id)
    return remove_from_cart(request, recipe_id)
