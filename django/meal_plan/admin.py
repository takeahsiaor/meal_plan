from django.contrib import admin
from .models import (
    Recipe,
    Tag,
    Plan,
    Ingredient,
    RecipeIngredient,
    Store,
    StoreIngredient,
)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ["name"]
    search_fields = ["name"]
    ordering = ["name"]


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = ["name", "brand", "is_staple"]
    list_filter = ["is_staple"]
    search_fields = ["name", "brand"]
    list_editable = ["is_staple"]
    ordering = ["name"]


class RecipeIngredientInline(admin.TabularInline):
    model = RecipeIngredient
    extra = 1
    autocomplete_fields = ["ingredient"]


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ["name", "last_used_on"]
    list_filter = ["tags"]
    search_fields = ["name"]
    filter_horizontal = ["tags"]
    readonly_fields = ["id"]
    inlines = [RecipeIngredientInline]
    date_hierarchy = "last_used_on"
    ordering = ["name"]


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ["plan_date"]
    filter_horizontal = ["recipes"]
    readonly_fields = ["id"]
    date_hierarchy = "plan_date"
    ordering = ["-plan_date"]


class StoreIngredientInline(admin.TabularInline):
    model = StoreIngredient
    extra = 1
    autocomplete_fields = ["ingredient"]


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ["name", "priority"]
    list_editable = ["priority"]
    readonly_fields = ["id"]
    search_fields = ["name"]
    inlines = [StoreIngredientInline]
    ordering = ["priority"]
    search_fields = ["name"]


@admin.register(StoreIngredient)
class StoreIngredientAdmin(admin.ModelAdmin):
    list_display = ["store", "ingredient", "is_preferred"]
    list_filter = ["store", "is_preferred"]
    list_editable = ["is_preferred"]
    search_fields = ["store__name", "ingredient__name"]
    autocomplete_fields = ["store", "ingredient"]
    ordering = ["store__priority", "ingredient__name"]


@admin.register(RecipeIngredient)
class RecipeIngredientAdmin(admin.ModelAdmin):
    list_display = ["recipe", "ingredient"]
    list_filter = ["recipe", "ingredient"]
    search_fields = ["recipe__name", "ingredient__name"]
    autocomplete_fields = ["recipe", "ingredient"]
    ordering = ["recipe__name", "ingredient__name"]
