import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

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

    def table_exists(name: str) -> bool:
        row = cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (name,),
        ).fetchone()
        return row is not None

    def column_exists(table: str, column: str) -> bool:
        info = cursor.execute(f"PRAGMA table_info({table})").fetchall()
        return any(r[1] == column for r in info)

    # Hard-remove migration:
    # - remove `shopping_list` (shopping list feature)
    # - remove `recipes.is_favorite` (favorites feature)
    # - add `recipes.meal_slot`
    # - add new `meal_plan` table
    need_rebuild = False
    if table_exists("recipes"):
        if column_exists("recipes", "is_favorite"):
            need_rebuild = True
        if not column_exists("recipes", "meal_slot"):
            need_rebuild = True
    else:
        need_rebuild = True

    if table_exists("shopping_list"):
        need_rebuild = True

    # Rebuild when any of the expected schema elements are missing.
    if need_rebuild:
        # Drop tables in dependency order.
        cursor.execute("DROP TABLE IF EXISTS meal_plan")
        cursor.execute("DROP TABLE IF EXISTS shopping_list")
        cursor.execute("DROP TABLE IF EXISTS recipes")

        cursor.execute(
            """
            CREATE TABLE recipes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                meal_slot TEXT NOT NULL,
                image_url TEXT NOT NULL,
                ingredients_json TEXT NOT NULL,
                steps_json TEXT NOT NULL,
                servings INTEGER NOT NULL DEFAULT 2,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE meal_plan (
                day_index INTEGER NOT NULL,
                meal_slot TEXT NOT NULL,
                recipe_id INTEGER NOT NULL,
                PRIMARY KEY(day_index, meal_slot),
                FOREIGN KEY(recipe_id) REFERENCES recipes(id) ON DELETE CASCADE
            )
            """
        )

        cursor.execute("CREATE INDEX idx_recipes_title ON recipes(title)")
        cursor.execute("CREATE INDEX idx_recipes_category ON recipes(category)")
        cursor.execute("CREATE INDEX idx_recipes_meal_slot ON recipes(meal_slot)")
        cursor.execute("CREATE INDEX idx_meal_plan_recipe ON meal_plan(recipe_id)")

        # Seed sample recipes.
        def map_slot_from_category(category: str) -> str:
            c = (category or "").strip().lower()
            if c in {"breakfast"}:
                return "Frühstück"
            if c in {"lunch"}:
                return "Mittag"
            if c in {"dinner"}:
                return "Abend"
            if "snack" in c:
                return "Snacks"
            # Default slot.
            return "Abend"

        sample_recipes = [
            {
                "title": "Käse-Tomaten-Pasta",
                "category": "Dinner",
                "meal_slot": map_slot_from_category("Dinner"),
                "image_url": "/static/images/placeholder.svg",
                "servings": 2,
                "ingredients": [
                    {"name": "Pasta", "amount": 200, "unit": "g"},
                    {"name": "Tomatensoße", "amount": 250, "unit": "ml"},
                    {"name": "Knoblauch", "amount": 2, "unit": "Zehen"},
                    {"name": "Parmesan", "amount": 40, "unit": "g"},
                ],
                "steps": [
                    "Pasta in Salzwasser al dente kochen.",
                    "Knoblauch kurz in etwas Öl anbraten (ca. 1 Minute).",
                    "Tomatensoße hinzufügen und 5 Minuten köcheln lassen.",
                    "Pasta mit Soße mischen und Parmesan darüber geben.",
                ],
            },
            {
                "title": "Griechische Joghurt-Bowl",
                "category": "Breakfast",
                "meal_slot": map_slot_from_category("Breakfast"),
                "image_url": "/static/images/placeholder.svg",
                "servings": 1,
                "ingredients": [
                    {"name": "Griechischer Joghurt", "amount": 200, "unit": "g"},
                    {"name": "Blaubeeren", "amount": 60, "unit": "g"},
                    {"name": "Honig", "amount": 1, "unit": "EL"},
                    {"name": "Granola", "amount": 40, "unit": "g"},
                ],
                "steps": [
                    "Joghurt in eine Schüssel geben.",
                    "Blaubeeren und Granola darüber verteilen.",
                    "Honig drüber geben und direkt essen.",
                ],
            },
            {
                "title": "Avocado-Hähnchensalat",
                "category": "Lunch",
                "meal_slot": map_slot_from_category("Lunch"),
                "image_url": "/static/images/placeholder.svg",
                "servings": 2,
                "ingredients": [
                    {"name": "Hähnchenbrust", "amount": 250, "unit": "g"},
                    {"name": "Avocado", "amount": 1, "unit": "Stk"},
                    {"name": "Gemischter Salat", "amount": 120, "unit": "g"},
                    {"name": "Zitronensaft", "amount": 2, "unit": "EL"},
                ],
                "steps": [
                    "Hähnchenbrust garen und in Stücke schneiden.",
                    "Salat, Avocado und Zitronensaft mischen.",
                    "Hähnchen obenauf geben und vorsichtig vermengen.",
                ],
            },
            {
                "title": "Banane-Schoko-Snack",
                "category": "Snack",
                "meal_slot": map_slot_from_category("Snack"),
                "image_url": "/static/images/placeholder.svg",
                "servings": 1,
                "ingredients": [
                    {"name": "Banane", "amount": 1, "unit": "Stk"},
                    {"name": "Kakaopulver", "amount": 1, "unit": "EL"},
                    {"name": "Honig", "amount": 1, "unit": "TL"},
                ],
                "steps": [
                    "Banane in Scheiben schneiden.",
                    "Mit Kakaopulver bestäuben und Honig darüber geben.",
                    "Kurz ziehen lassen und genießen.",
                ],
            },
        ]

        # Insert recipes.
        recipe_ids: List[int] = []
        for recipe in sample_recipes:
            cursor.execute(
                """
                INSERT INTO recipes(title, category, meal_slot, image_url, ingredients_json, steps_json, servings)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    recipe["title"],
                    recipe["category"],
                    recipe["meal_slot"],
                    recipe["image_url"],
                    json.dumps(recipe["ingredients"]),
                    json.dumps(recipe["steps"]),
                    recipe["servings"],
                ),
            )
            recipe_ids.append(cursor.lastrowid)

        # Seed a small meal plan: first week entries.
        # day_index 0..6 (Mo..So), assign one recipe per meal_slot.
        cursor.execute(
            "SELECT id, meal_slot FROM recipes"
        )
        rows = cursor.fetchall()
        by_slot: Dict[str, int] = {r[1]: r[0] for r in rows}
        slots = ["Frühstück", "Mittag", "Abend", "Snacks"]
        for day_index in range(7):
            # Only assign slots we have recipes for.
            for slot in slots:
                rid = by_slot.get(slot)
                if rid is not None:
                    cursor.execute(
                        "INSERT OR REPLACE INTO meal_plan(day_index, meal_slot, recipe_id) VALUES (?, ?, ?)",
                        (day_index, slot, rid),
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
        "meal_slot": row["meal_slot"],
        "image_url": row["image_url"],
        "ingredients": json.loads(row["ingredients_json"]),
        "steps": json.loads(row["steps_json"]),
        "servings": row["servings"],
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

