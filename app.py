import json
import sqlite3
from pathlib import Path
from typing import Dict, List

from flask import Flask, g, jsonify, render_template, request

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "cookmind.db"

app = Flask(__name__)


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    db = sqlite3.connect(DB_PATH)
    cursor = db.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS recipes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            image_url TEXT NOT NULL,
            ingredients_json TEXT NOT NULL,
            steps_json TEXT NOT NULL,
            servings INTEGER NOT NULL DEFAULT 2,
            is_favorite INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS shopping_list (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ingredient_name TEXT NOT NULL UNIQUE,
            amount REAL DEFAULT 1,
            unit TEXT DEFAULT '',
            bought INTEGER NOT NULL DEFAULT 0
        )
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_recipes_title ON recipes(title)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_recipes_category ON recipes(category)
        """
    )

    cursor.execute("SELECT COUNT(*) AS total FROM recipes")
    total = cursor.fetchone()[0]

    if total == 0:
        sample_recipes = [
            {
                "title": "Creamy Tomato Pasta",
                "category": "Dinner",
                "image_url": "https://images.unsplash.com/photo-1621996346565-e3dbc646d9a9?auto=format&fit=crop&w=1200&q=80",
                "servings": 2,
                "ingredients": [
                    {"name": "Pasta", "amount": 200, "unit": "g"},
                    {"name": "Tomato Sauce", "amount": 250, "unit": "ml"},
                    {"name": "Garlic", "amount": 2, "unit": "cloves"},
                    {"name": "Parmesan", "amount": 40, "unit": "g"},
                ],
                "steps": [
                    "Cook pasta in salted water until al dente.",
                    "Saute garlic in olive oil for 1 minute.",
                    "Add tomato sauce and simmer for 5 minutes.",
                    "Combine pasta with sauce and top with parmesan.",
                ],
            },
            {
                "title": "Greek Yogurt Bowl",
                "category": "Breakfast",
                "image_url": "https://images.unsplash.com/photo-1490474418585-ba9bad8fd0ea?auto=format&fit=crop&w=1200&q=80",
                "servings": 1,
                "ingredients": [
                    {"name": "Greek Yogurt", "amount": 200, "unit": "g"},
                    {"name": "Blueberries", "amount": 60, "unit": "g"},
                    {"name": "Honey", "amount": 1, "unit": "tbsp"},
                    {"name": "Granola", "amount": 40, "unit": "g"},
                ],
                "steps": [
                    "Add yogurt to a bowl.",
                    "Top with blueberries and granola.",
                    "Drizzle honey over the top and serve.",
                ],
            },
            {
                "title": "Avocado Chicken Salad",
                "category": "Lunch",
                "image_url": "https://images.unsplash.com/photo-1546793665-c74683f339c1?auto=format&fit=crop&w=1200&q=80",
                "servings": 2,
                "ingredients": [
                    {"name": "Chicken Breast", "amount": 250, "unit": "g"},
                    {"name": "Avocado", "amount": 1, "unit": "pcs"},
                    {"name": "Mixed Greens", "amount": 120, "unit": "g"},
                    {"name": "Lemon Juice", "amount": 2, "unit": "tbsp"},
                ],
                "steps": [
                    "Cook and slice chicken breast.",
                    "Mix greens, avocado, and lemon juice.",
                    "Add chicken on top and toss gently.",
                ],
            },
        ]

        for recipe in sample_recipes:
            cursor.execute(
                """
                INSERT INTO recipes(title, category, image_url, ingredients_json, steps_json, servings)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    recipe["title"],
                    recipe["category"],
                    recipe["image_url"],
                    json.dumps(recipe["ingredients"]),
                    json.dumps(recipe["steps"]),
                    recipe["servings"],
                ),
            )

    db.commit()
    db.close()


def parse_recipe_row(row: sqlite3.Row) -> Dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "category": row["category"],
        "image_url": row["image_url"],
        "ingredients": json.loads(row["ingredients_json"]),
        "steps": json.loads(row["steps_json"]),
        "servings": row["servings"],
        "is_favorite": bool(row["is_favorite"]),
    }


def merge_ingredients(ingredients: List[Dict]) -> List[Dict]:
    merged = {}
    for ingredient in ingredients:
        key = ingredient["name"].strip().lower()
        unit = ingredient.get("unit", "").strip()
        amount = float(ingredient.get("amount", 1) or 1)
        if key not in merged:
            merged[key] = {
                "ingredient_name": ingredient["name"].strip(),
                "amount": amount,
                "unit": unit,
            }
        else:
            merged[key]["amount"] += amount
    return list(merged.values())


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/recipes", methods=["GET"])
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
        recipes = [
            r
            for r in recipes
            if any(ingredient in i["name"].lower() for i in r["ingredients"])
        ]

    return jsonify(recipes)


@app.route("/api/recipes/<int:recipe_id>", methods=["GET"])
def get_recipe(recipe_id: int):
    db = get_db()
    row = db.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
    if not row:
        return jsonify({"error": "Recipe not found"}), 404
    return jsonify(parse_recipe_row(row))


@app.route("/api/recipes", methods=["POST"])
def add_recipe():
    payload = request.get_json(force=True)
    title = payload.get("title", "").strip()
    category = payload.get("category", "").strip() or "General"
    image_url = payload.get("image_url", "").strip() or "https://images.unsplash.com/photo-1495195134817-aeb325a55b65?auto=format&fit=crop&w=1200&q=80"
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


@app.route("/api/favorites/<int:recipe_id>", methods=["POST"])
def toggle_favorite(recipe_id: int):
    db = get_db()
    row = db.execute("SELECT is_favorite FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
    if not row:
        return jsonify({"error": "Recipe not found"}), 404
    next_value = 0 if row["is_favorite"] else 1
    db.execute("UPDATE recipes SET is_favorite = ? WHERE id = ?", (next_value, recipe_id))
    db.commit()
    return jsonify({"recipe_id": recipe_id, "is_favorite": bool(next_value)})


@app.route("/api/favorites", methods=["GET"])
def get_favorites():
    db = get_db()
    rows = db.execute("SELECT * FROM recipes WHERE is_favorite = 1 ORDER BY created_at DESC").fetchall()
    return jsonify([parse_recipe_row(row) for row in rows])


@app.route("/api/shopping-list", methods=["GET"])
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


@app.route("/api/shopping-list/from-recipe/<int:recipe_id>", methods=["POST"])
def add_recipe_ingredients_to_shopping_list(recipe_id: int):
    db = get_db()
    row = db.execute("SELECT ingredients_json FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
    if not row:
        return jsonify({"error": "Recipe not found"}), 404

    ingredients = merge_ingredients(json.loads(row["ingredients_json"]))
    for ingredient in ingredients:
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


@app.route("/api/shopping-list/<int:item_id>/toggle", methods=["POST"])
def toggle_shopping_item(item_id: int):
    db = get_db()
    row = db.execute("SELECT bought FROM shopping_list WHERE id = ?", (item_id,)).fetchone()
    if not row:
        return jsonify({"error": "Shopping item not found"}), 404
    next_value = 0 if row["bought"] else 1
    db.execute("UPDATE shopping_list SET bought = ? WHERE id = ?", (next_value, item_id))
    db.commit()
    return jsonify({"id": item_id, "bought": bool(next_value)})


@app.route("/api/suggest-recipes", methods=["POST"])
def suggest_recipes():
    payload = request.get_json(force=True)
    available = payload.get("ingredients", "")
    available_set = {item.strip().lower() for item in available.split(",") if item.strip()}
    if not available_set:
        return jsonify([])

    db = get_db()
    rows = db.execute("SELECT * FROM recipes").fetchall()
    scored = []

    for row in rows:
        recipe = parse_recipe_row(row)
        recipe_ingredients = {item["name"].strip().lower() for item in recipe["ingredients"]}
        matches = recipe_ingredients.intersection(available_set)
        if matches:
            score = len(matches) / max(len(recipe_ingredients), 1)
            scored.append(
                {
                    "score": round(score, 2),
                    "matched_ingredients": sorted(list(matches)),
                    "recipe": recipe,
                }
            )

    scored.sort(key=lambda x: x["score"], reverse=True)
    return jsonify(scored[:5])


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
