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
from .models import Ingredient, Plan, Recipe, Store, StoreIngredient, Tag


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


def _build_plan_shopping_list(plan):
    """
    Build shopping list for a plan: ingredients grouped by store.
    Returns list of (store, items) where items is list of (ingredient, recipe_names, is_staple).
    Uses store priority and minimizes number of stores; staples marked optional.
    """
    recipes = list(plan.recipes.prefetch_related("ingredients").order_by("name"))
    if not recipes:
        return []

    # Collect (ingredient, list of recipe names) for all ingredients in the plan
    ing_to_recipes = {}  # ingredient_id -> (Ingredient, set of recipe names)
    for recipe in recipes:
        for ing in recipe.ingredients.all():
            if ing.id not in ing_to_recipes:
                ing_to_recipes[ing.id] = [ing, set()]
            ing_to_recipes[ing.id][1].add(recipe.name)

    our_ingredient_ids = set(ing_to_recipes.keys())
    if not our_ingredient_ids:
        return []

    # All stores by priority (lower priority value = higher priority)
    stores = list(Store.objects.prefetch_related("ingredients").order_by("priority"))
    store_ingredient_ids = {s.id: set(s.ingredients.values_list("id", flat=True)) for s in stores}

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

    # For each ingredient, get list of (Store, our_count, is_preferred) that have it, sorted by (priority, -preferred, -our_count)
    ing_to_stores = {}  # ingredient_id -> list of (Store, our_count, is_preferred)
    for ing_id, (ing, _) in ing_to_recipes.items():
        options = [
            (s, our_count(s.id), (ing_id, s.id) in preferred_pairs)
            for s in stores
            if ing_id in store_ingredient_ids.get(s.id, set())
        ]
        options.sort(key=lambda x: (x[0].priority, -x[2], -x[1]))
        ing_to_stores[ing_id] = options

    # Assign each ingredient to one store: single-store forces that store; else prefer store we're already using
    assigned = {}  # ingredient_id -> Store
    used_stores = set()

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
        # Prefer a store we're already using that has is_preferred for this ingredient
        for s, _, is_preferred in options:
            if s.id in used_stores and is_preferred:
                assigned[ing_id] = s
                break
        else:
            # Else prefer any store we're already using
            for s, _, _ in options:
                if s.id in used_stores:
                    assigned[ing_id] = s
                    break
            else:
                s = options[0][0]
                assigned[ing_id] = s
                used_stores.add(s.id)

    # Ingredients in no store: assign to None (display as "Other" or similar)
    for ing_id in our_ingredient_ids:
        if ing_id not in assigned:
            assigned[ing_id] = None

    # Build output by store: (store, [(ingredient, recipe_names, is_staple, color_class), ...])
    recipe_colors = [
        "primary", "success", "info", "warning", "danger", "secondary", "dark",
    ]
    recipe_to_color = {
        r.name: recipe_colors[i % len(recipe_colors)]
        for i, r in enumerate(sorted(recipes, key=lambda x: x.name))
    }

    store_to_items = {}  # store_id or "other" -> (Store or None, list)
    for store in stores:
        if store.id in used_stores:
            store_to_items[store.id] = (store, [])
    store_to_items["other"] = (None, [])

    for ing_id in our_ingredient_ids:
        ing, recipe_names = ing_to_recipes[ing_id]
        store = assigned[ing_id]
        names_sorted = sorted(recipe_names)
        color = recipe_to_color.get(names_sorted[0], "secondary") if names_sorted else "secondary"
        entry = (ing, names_sorted, ing.is_staple, color)
        if store is None:
            store_to_items["other"][1].append(entry)
        else:
            store_to_items[store.id][1].append(entry)

    # Order: required stores first (by priority), then "other" if any
    result = []
    for store in stores:
        if store.id in store_to_items:
            items = store_to_items[store.id][1]
            if items:
                result.append(
                    (store_to_items[store.id][0], sorted(items, key=lambda x: ((x[1][0] if x[1] else "", x[2], x[0].name))))
                )
    if store_to_items["other"][1]:
        result.append(
            (None, sorted(store_to_items["other"][1], key=lambda x: ((x[1][0] if x[1] else "", x[2], x[0].name))))
        )
    return result


def plan_detail(request, plan_id):
    plan = get_object_or_404(
        Plan.objects.prefetch_related("recipes__ingredients"),
        id=plan_id,
    )
    shopping_by_store = _build_plan_shopping_list(plan)
    recipes = list(plan.recipes.prefetch_related("ingredients").order_by("name"))
    recipe_colors = [
        "primary", "success", "info", "warning", "danger", "secondary", "dark",
    ]
    recipe_to_color = {r.name: recipe_colors[i % len(recipe_colors)] for i, r in enumerate(recipes)}
    recipe_color_pairs = [(r, recipe_to_color[r.name]) for r in recipes]
    tab_param = request.GET.get("tab", "shopping")
    active_tab = "recipes" if tab_param == "recipes" else "shopping"
    return render(
        request,
        "meal_plan/plan_detail.html",
        {
            "plan": plan,
            "recipes": recipes,
            "recipe_color_pairs": recipe_color_pairs,
            "shopping_by_store": shopping_by_store,
            "recipe_to_color": recipe_to_color,
            "active_tab": active_tab,
        },
    )


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
