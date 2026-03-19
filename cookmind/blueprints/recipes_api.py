import json
from typing import Any, Dict

from flask import Blueprint, jsonify, request

from ..db import get_db, parse_recipe_row

recipes_api = Blueprint("recipes_api", __name__)


@recipes_api.route("/api/recipes", methods=["GET"])
def get_recipes():
    db = get_db()
    search = request.args.get("q", "").strip().lower()
    category = request.args.get("category", "").strip().lower()
    ingredient = request.args.get("ingredient", "").strip().lower()

    rows = db.execute("SELECT * FROM recipes ORDER BY created_at DESC").fetchall()
    recipes = [parse_recipe_row(row) for row in rows]

    if search:
        recipes = [r for r in recipes if search in r["title"].lower()]
    if category:
        recipes = [r for r in recipes if category in r["category"].lower()]
    if ingredient:
        # Ingredient filter is treated as a comma-separated list of tokens.
        # A recipe matches when at least one token is found in one of its ingredient names.
        tokens = [t.strip() for t in ingredient.replace(";", ",").split(",") if t.strip()]
        tokens = [t.lower() for t in tokens]

        def recipe_matches_token(recipe: Dict[str, Any]) -> bool:
            ingredient_names = [i["name"].lower() for i in recipe.get("ingredients", []) if i.get("name")]
            return any(any(token in name for name in ingredient_names) for token in tokens)

        recipes = [r for r in recipes if recipe_matches_token(r)]

    return jsonify(recipes)


@recipes_api.route("/api/recipes/<int:recipe_id>", methods=["GET"])
def get_recipe(recipe_id: int):
    db = get_db()
    row = db.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
    if not row:
        return jsonify({"error": "Recipe not found"}), 404
    return jsonify(parse_recipe_row(row))


@recipes_api.route("/api/recipes", methods=["POST"])
def add_recipe():
    payload: Dict[str, Any] = request.get_json(force=True)
    title = (payload.get("title") or "").strip()
    category = (payload.get("category") or "").strip() or "General"
    image_url = (payload.get("image_url") or "").strip() or "/static/images/placeholder.svg"
    servings = int(payload.get("servings") or 2)
    ingredients = payload.get("ingredients") or []
    steps = payload.get("steps") or []

    if not title or not ingredients or not steps:
        return jsonify({"error": "Title, ingredients, and steps are required."}), 400

    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        """
        INSERT INTO recipes(title, category, image_url, ingredients_json, steps_json, servings)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (title, category, image_url, json.dumps(ingredients), json.dumps(steps), servings),
    )
    db.commit()
    recipe_id = cursor.lastrowid
    row = db.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
    return jsonify(parse_recipe_row(row)), 201

