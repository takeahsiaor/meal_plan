"""
Data structures for PlanShoppingList.list_items JSON field.

Structure:
    {
        "<store uuid>": {
            "ingredients": [{"name": str, "recipes": [...], "is_staple": bool, "ingredient_id": "<uuid>"}, ...],
            "is_manual": bool,  # True if store was added by user (e.g. "Add store" button)
        },
        ...
    }
"""
from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class ShoppingListItem:
    """One ingredient entry under a store in the shopping list."""

    name: str
    recipes: tuple[str, ...]  # recipe names, sorted
    is_staple: bool
    ingredient_id: Optional[str] = None  # Ingredient PK for lookups

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"name": self.name, "recipes": list(self.recipes), "is_staple": self.is_staple}
        if self.ingredient_id is not None:
            d["ingredient_id"] = self.ingredient_id
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ShoppingListItem":
        return cls(
            name=data["name"],
            recipes=tuple(data.get("recipes", [])),
            is_staple=data.get("is_staple", False),
            ingredient_id=data.get("ingredient_id"),
        )


def serialize_list_items(
    store_to_data: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """
    Convert typed structure to JSON-serializable dict for storage.
    store_to_data: { store_key: {"ingredients": list[ShoppingListItem], "is_manual": bool} }
    Returns: { store_key: {"ingredients": [item.to_dict(), ...], "is_manual": bool} }
    """
    result: dict[str, dict[str, Any]] = {}
    for store_key, data in store_to_data.items():
        ingredients = data.get("ingredients", [])
        result[store_key] = {
            "ingredients": [item.to_dict() for item in ingredients],
            "is_manual": bool(data.get("is_manual", False)),
        }
    return result
