import json
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from flask import Blueprint, jsonify, request
from werkzeug.utils import secure_filename

from ..db import get_db, parse_recipe_row

recipes_api = Blueprint("recipes_api", __name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
UPLOAD_DIR = PROJECT_ROOT / "static" / "images" / "uploads"


def _parse_json_or_form() -> Dict[str, Any]:
    """
    Supports:
    - JSON payloads (application/json)
    - FormData payloads (multipart/form-data) where `ingredients` and `steps`
      are JSON-encoded strings.
    """
    if request.is_json:
        return request.get_json(silent=True) or {}

    form = request.form or {}
    payload: Dict[str, Any] = {}
    payload["title"] = (form.get("title") or "").strip()
    payload["category"] = (form.get("category") or "").strip()
    payload["meal_slot"] = (form.get("meal_slot") or "").strip()
    payload["image_url"] = (form.get("image_url") or "").strip()
    payload["servings"] = form.get("servings") or ""

    ingredients_raw = form.get("ingredients")
    steps_raw = form.get("steps")
    try:
        payload["ingredients"] = json.loads(ingredients_raw) if ingredients_raw else []
    except json.JSONDecodeError:
        payload["ingredients"] = []

    try:
        payload["steps"] = json.loads(steps_raw) if steps_raw else []
    except json.JSONDecodeError:
        payload["steps"] = []

    return payload


def _save_image_file(image_file) -> Optional[str]:
    """
    Saves an uploaded image and returns the URL path stored in DB (e.g. /static/images/uploads/<file>).
    """
    if image_file is None:
        return None
    filename = getattr(image_file, "filename", None)
    if not filename:
        return None

    safe_name = secure_filename(filename)
    if not safe_name:
        return None

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    unique = uuid.uuid4().hex
    final_name = f"{unique}_{safe_name}"
    image_path = UPLOAD_DIR / final_name
    image_file.save(str(image_path))
    return f"/static/images/uploads/{final_name}"


@recipes_api.route("/api/recipes", methods=["GET"])
def get_recipes():
    db = get_db()
    search = request.args.get("q", "").strip().lower()
    category = request.args.get("category", "").strip().lower()
    ingredient = request.args.get("ingredient", "").strip().lower()
    meal_slot = request.args.get("meal_slot", "").strip().lower()

    rows = db.execute("SELECT * FROM recipes ORDER BY created_at DESC").fetchall()
    recipes = [parse_recipe_row(row) for row in rows]

    if search:
        recipes = [r for r in recipes if search in r["title"].lower()]
    if category:
        recipes = [r for r in recipes if category in r["category"].lower()]
    if meal_slot:
        recipes = [r for r in recipes if str(r.get("meal_slot", "")).lower() == meal_slot]
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
    payload = _parse_json_or_form()
    title = (payload.get("title") or "").strip()
    category = (payload.get("category") or "").strip() or "General"
    meal_slot = (payload.get("meal_slot") or "").strip() or "Abend"
    servings = int(payload.get("servings") or 2)
    ingredients: List[Dict[str, Any]] = payload.get("ingredients") or []
    steps: List[str] = payload.get("steps") or []

    # Image upload (multipart) has priority; otherwise use image_url or placeholder.
    uploaded_url = _save_image_file(request.files.get("image_file"))
    image_url = uploaded_url or (payload.get("image_url") or "").strip() or "/static/images/placeholder.svg"

    if not title or not ingredients or not steps:
        return jsonify({"error": "Title, ingredients, and steps are required."}), 400

    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        """
        INSERT INTO recipes(title, category, meal_slot, image_url, ingredients_json, steps_json, servings)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (title, category, meal_slot, image_url, json.dumps(ingredients), json.dumps(steps), servings),
    )
    db.commit()
    recipe_id = cursor.lastrowid
    row = db.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
    return jsonify(parse_recipe_row(row)), 201


@recipes_api.route("/api/recipes/<int:recipe_id>", methods=["PUT"])
def update_recipe(recipe_id: int):
    payload = _parse_json_or_form()
    db = get_db()

    existing = db.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
    if not existing:
        return jsonify({"error": "Recipe not found"}), 404

    title = (payload.get("title") or "").strip()
    category = (payload.get("category") or "").strip() or existing["category"]
    meal_slot = (payload.get("meal_slot") or "").strip() or existing["meal_slot"] or "Abend"
    servings = int(payload.get("servings") or existing["servings"] or 2)
    ingredients: List[Dict[str, Any]] = payload.get("ingredients") or []
    steps: List[str] = payload.get("steps") or []

    uploaded_url = _save_image_file(request.files.get("image_file"))
    provided_image_url = (payload.get("image_url") or "").strip()

    # Only overwrite image_url when:
    # - a new upload happened OR
    # - an explicit image_url was provided (can be the same as before).
    image_url = existing["image_url"]
    if uploaded_url:
        image_url = uploaded_url
    elif provided_image_url:
        image_url = provided_image_url

    if not title or not ingredients or not steps:
        return jsonify({"error": "Title, ingredients, and steps are required."}), 400

    db.execute(
        """
        UPDATE recipes
        SET title = ?,
            category = ?,
            meal_slot = ?,
            image_url = ?,
            ingredients_json = ?,
            steps_json = ?,
            servings = ?
        WHERE id = ?
        """,
        (
            title,
            category,
            meal_slot,
            image_url,
            json.dumps(ingredients),
            json.dumps(steps),
            servings,
            recipe_id,
        ),
    )
    db.commit()

    row = db.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
    return jsonify(parse_recipe_row(row))


@recipes_api.route("/api/recipes/<int:recipe_id>", methods=["DELETE"])
def delete_recipe(recipe_id: int):
    db = get_db()
    existing = db.execute("SELECT id FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
    if not existing:
        return jsonify({"error": "Recipe not found"}), 404

    db.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))
    db.commit()
    return jsonify({"deleted": True, "recipe_id": recipe_id})

