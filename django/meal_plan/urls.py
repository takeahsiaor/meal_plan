from django.urls import path

from . import views

app_name = "meal_plan"

urlpatterns = [
    path("plans/", views.PlanListView.as_view(), name="plan_list"),
    path("plans/<uuid:plan_id>/", views.plan_detail, name="plan_detail"),
    path("plans/<uuid:plan_id>/delete/", views.plan_delete, name="plan_delete"),
    path("recipes/", views.RecipeListView.as_view(), name="recipe_list"),
    path("recipes/<uuid:recipe_id>/detail/", views.recipe_detail_json, name="recipe_detail"),
    path("recipes/cart/", views.CartView.as_view(), name="cart"),
    path("recipes/cart/add/<uuid:recipe_id>/", views.add_to_cart_view, name="add_to_cart"),
    path("recipes/cart/remove/<uuid:recipe_id>/", views.remove_from_cart_view, name="remove_from_cart"),
]
