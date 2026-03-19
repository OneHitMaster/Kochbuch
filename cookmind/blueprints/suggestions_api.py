from typing import Any, Dict, List, Set

from flask import Blueprint, jsonify, request

from ..db import get_db, parse_recipe_row

suggestions_api = Blueprint("suggestions_api", __name__)


@suggestions_api.route("/api/suggest-recipes", methods=["POST"])
def suggest_recipes():
    payload: Dict[str, Any] = request.get_json(force=True)
    available = payload.get("ingredients", "")
    available_set: Set[str] = {item.strip().lower() for item in str(available).split(",") if item.strip()}
    if not available_set:
        return jsonify([])

    db = get_db()
    rows = db.execute("SELECT * FROM recipes").fetchall()
    scored: List[Dict[str, Any]] = []

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

