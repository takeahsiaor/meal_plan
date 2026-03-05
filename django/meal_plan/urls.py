from django.urls import path

from . import views

app_name = "meal_plan"

urlpatterns = [
    path("", views.RecipeListView.as_view(), name="index"),
    path("plans/", views.PlanListView.as_view(), name="plan_list"),
    path("plans/<uuid:plan_id>/", views.plan_detail, name="plan_detail"),
    path("plans/<uuid:plan_id>/delete/", views.plan_delete, name="plan_delete"),
    path("plans/<uuid:plan_id>/recipes/remove/<uuid:recipe_id>/", views.plan_remove_recipe, name="plan_remove_recipe"),
    path("plans/<uuid:plan_id>/recipes/add/", views.plan_add_recipe, name="plan_add_recipe"),
    path("plans/<uuid:plan_id>/recipes/<uuid:recipe_id>/notes/", views.plan_update_recipe_notes, name="plan_update_recipe_notes"),
    path("plans/<uuid:plan_id>/recipes/<uuid:recipe_id>/prep-notes/", views.plan_update_recipe_prep_notes, name="plan_update_recipe_prep_notes"),
    path("plans/<uuid:plan_id>/shopping-list/", views.plan_update_shopping_list, name="plan_update_shopping_list"),
    path("plans/<uuid:plan_id>/shopping-list/recalculate-stores/", views.plan_recalculate_stores, name="plan_recalculate_stores"),
    path("plans/<uuid:plan_id>/shopping-list/reset/", views.plan_reset_shopping_list, name="plan_reset_shopping_list"),
    path("shopping-list/validate-ingredient-store/", views.validate_ingredient_store, name="validate_ingredient_store"),
    path("ingredients/search/", views.ingredient_search, name="ingredient_search"),
    path("recipes/search/", views.recipe_search, name="recipe_search"),
    path("recipes/", views.RecipeListView.as_view(), name="recipe_list"),
    path("recipes/<uuid:recipe_id>/detail/", views.recipe_detail_json, name="recipe_detail"),
    path("recipes/cart/", views.CartView.as_view(), name="cart"),
    path("recipes/cart/add/<uuid:recipe_id>/", views.add_to_cart_view, name="add_to_cart"),
    path("recipes/cart/remove/<uuid:recipe_id>/", views.remove_from_cart_view, name="remove_from_cart"),
]
