"""
Data structures for PlanShoppingList JSON fields.

list_items:
    {
        "<store uuid>": {
            "ingredients": [{"name": str, "recipes": [...], "is_staple": bool, "ingredient_id": "<uuid>", "quantity": str}, ...],
            "is_manual": bool,  # True if store was added by user (e.g. "Add store" button)
            "trip_date": str,   # "YYYY-MM-DD" for when to visit the store
            "notes": str,       # notes for the store
        },
        ...
    }

removed_items: list of ingredients the user has explicitly removed, each entry is a ShoppingListItem dict plus store_id
    so the item can be put back into the correct store: [{"store_id": "<uuid>", "name": str, "recipes": [...],
    "is_staple": bool, "ingredient_id": "<uuid>" (optional), "quantity": str (optional), "is_manual": bool}, ...]
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
    quantity: Optional[str] = None
    is_manual: bool = False

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "name": self.name,
            "recipes": list(self.recipes),
            "is_staple": self.is_staple,
            "quantity": self.quantity,
            "is_manual": self.is_manual,
        }
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
            quantity=data.get("quantity"),
            is_manual=data.get("is_manual", False),
        )


def serialize_list_items(
    store_to_data: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """
    Convert typed structure to JSON-serializable dict for storage.
    store_to_data: { store_key: {"ingredients": list[ShoppingListItem], "is_manual": bool, "trip_date": str} }
    Returns: { store_key: {"ingredients": [...], "is_manual": bool, "trip_date": str} }
    """
    result: dict[str, dict[str, Any]] = {}
    for store_key, data in store_to_data.items():
        ingredients = data.get("ingredients", [])
        result[store_key] = {
            "ingredients": [item.to_dict() for item in ingredients],
            "is_manual": bool(data.get("is_manual", False)),
            "trip_date": data.get("trip_date") if isinstance(data.get("trip_date"), str) else None,
            "notes": data.get("notes") if isinstance(data.get("notes"), str) else None,
        }
    return result
