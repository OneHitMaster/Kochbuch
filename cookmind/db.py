import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List

from flask import g

BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "cookmind.db"


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


def init_db() -> None:
    # Open a separate connection for initialization.
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

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_recipes_title ON recipes(title)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_recipes_category ON recipes(category)")

    cursor.execute("SELECT COUNT(*) AS total FROM recipes")
    total = cursor.fetchone()[0]

    if total == 0:
        sample_recipes = [
            {
                "title": "Creamy Tomato Pasta",
                "category": "Dinner",
                "image_url": "/static/images/placeholder.svg",
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
                "image_url": "/static/images/placeholder.svg",
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
                "image_url": "/static/images/placeholder.svg",
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


def close_db(exception: Any) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def parse_recipe_row(row: sqlite3.Row) -> Dict[str, Any]:
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


def merge_ingredients(ingredients: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Merge duplicate ingredient names (case-insensitive) by summing amounts.

    Notes:
    - We normalize based on ingredient `name` only.
    - Unit is kept from the first occurrence.
    """
    merged: Dict[str, Dict[str, Any]] = {}
    for ingredient in ingredients:
        key = (ingredient["name"] or "").strip().lower()
        unit = (ingredient.get("unit") or "").strip()
        amount = float(ingredient.get("amount", 1) or 1)

        if not key:
            continue

        if key not in merged:
            merged[key] = {
                "ingredient_name": (ingredient["name"] or "").strip(),
                "amount": amount,
                "unit": unit,
            }
        else:
            merged[key]["amount"] += amount
    return list(merged.values())

