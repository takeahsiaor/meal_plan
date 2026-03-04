from django.contrib import admin
from .models import (
    Recipe,
    Tag,
    Plan,
    PlanRecipe,
    PlanShoppingList,
    Ingredient,
    RecipeIngredient,
    Store,
    StoreIngredient,
)


class PlanRecipeInline(admin.TabularInline):
    model = PlanRecipe
    extra = 1
    autocomplete_fields = ["recipe"]


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
    readonly_fields = ["id"]
    date_hierarchy = "plan_date"
    ordering = ["-plan_date"]
    inlines = [PlanRecipeInline]
    search_fields = ["plan_date"]


@admin.register(PlanRecipe)
class PlanRecipeAdmin(admin.ModelAdmin):
    list_display = ["plan", "recipe", "notes"]
    list_filter = ["plan__plan_date"]
    search_fields = ["plan__plan_date", "recipe__name"]
    autocomplete_fields = ["plan", "recipe"]
    ordering = ["-plan__plan_date", "recipe__name"]


@admin.register(PlanShoppingList)
class PlanShoppingListAdmin(admin.ModelAdmin):
    list_display = ["plan", "plan_date"]
    list_filter = ["plan__plan_date"]
    readonly_fields = ["id"]
    date_hierarchy = "plan__plan_date"
    ordering = ["-plan__plan_date"]

    @admin.display(description="Plan date")
    def plan_date(self, obj):
        return obj.plan.plan_date if obj.plan_id else None


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
