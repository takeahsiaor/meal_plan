"""
Data structures for PlanShoppingList.list_items JSON field.

Structure:
    {
        "<store uuid>": [  # or "Other" for unassigned
            {"name": str, "recipes": [...], "is_staple": bool, "ingredient_id": "<uuid>"},
            ...
        ],
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


def serialize_list_items(store_to_items: dict[str, list[ShoppingListItem]]) -> dict[str, list[dict[str, Any]]]:
    """Convert typed structure to JSON-serializable dict for storage."""
    return {
        store_name: [item.to_dict() for item in items]
        for store_name, items in store_to_items.items()
    }


def deserialize_list_items(data: dict[str, Any]) -> dict[str, list[ShoppingListItem]]:
    """Parse stored JSON back into typed structure."""
    if not data:
        return {}
    return {
        store_name: [ShoppingListItem.from_dict(item) for item in items]
        for store_name, items in data.items()
    }
