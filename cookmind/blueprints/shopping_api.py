import json
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request

from ..db import get_db, merge_ingredients, parse_recipe_row

shopping_api = Blueprint("shopping_api", __name__)


@shopping_api.route("/api/shopping-list", methods=["GET"])
def get_shopping_list():
    db = get_db()
    rows = db.execute("SELECT * FROM shopping_list ORDER BY bought ASC, ingredient_name ASC").fetchall()
    return jsonify(
        [
            {
                "id": row["id"],
                "ingredient_name": row["ingredient_name"],
                "amount": row["amount"],
                "unit": row["unit"],
                "bought": bool(row["bought"]),
            }
            for row in rows
        ]
    )


@shopping_api.route("/api/shopping-list/from-recipe/<int:recipe_id>", methods=["POST"])
def add_recipe_ingredients_to_shopping_list(recipe_id: int):
    """
    Current behavior (will be enhanced in a later to-do):
    - If the client sends no payload, all recipe ingredients are added.
    - If the client sends a payload with `{"ingredients": [...]}`, only those ingredients
      are merged into the shopping list.
    """
    db = get_db()
    row = db.execute("SELECT ingredients_json FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
    if not row:
        return jsonify({"error": "Recipe not found"}), 404

    ingredients: List[Dict[str, Any]] = json.loads(row["ingredients_json"])

    # Optional payload with selected/scaled ingredients:
    # { "ingredients": [ { "name": "...", "amount": 2, "unit": "g" }, ... ] }
    payload: Optional[Dict[str, Any]] = request.get_json(silent=True)
    if payload is not None and isinstance(payload, dict) and "ingredients" in payload:
        selected_ingredients = payload.get("ingredients")
        if not isinstance(selected_ingredients, list):
            return jsonify({"error": "`ingredients` must be a list"}), 400
        if len(selected_ingredients) == 0:
            return jsonify({"error": "No ingredients selected"}), 400
        ingredients = selected_ingredients

    merged = merge_ingredients(ingredients)
    for ingredient in merged:
        existing = db.execute(
            "SELECT id, amount FROM shopping_list WHERE LOWER(ingredient_name) = LOWER(?)",
            (ingredient["ingredient_name"],),
        ).fetchone()
        if existing:
            db.execute(
                "UPDATE shopping_list SET amount = ?, bought = 0 WHERE id = ?",
                (existing["amount"] + ingredient["amount"], existing["id"]),
            )
        else:
            db.execute(
                """
                INSERT INTO shopping_list(ingredient_name, amount, unit, bought)
                VALUES (?, ?, ?, 0)
                """,
                (ingredient["ingredient_name"], ingredient["amount"], ingredient["unit"]),
            )

    db.commit()
    return jsonify({"message": "Ingredients added to shopping list"})


@shopping_api.route("/api/shopping-list/<int:item_id>/toggle", methods=["POST"])
def toggle_shopping_item(item_id: int):
    db = get_db()
    row = db.execute("SELECT bought FROM shopping_list WHERE id = ?", (item_id,)).fetchone()
    if not row:
        return jsonify({"error": "Shopping item not found"}), 404
    next_value = 0 if row["bought"] else 1
    db.execute("UPDATE shopping_list SET bought = ? WHERE id = ?", (next_value, item_id))
    db.commit()
    return jsonify({"id": item_id, "bought": bool(next_value)})

