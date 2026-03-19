from flask import Blueprint, jsonify

from ..db import get_db, parse_recipe_row

favorites_api = Blueprint("favorites_api", __name__)


@favorites_api.route("/api/favorites/<int:recipe_id>", methods=["POST"])
def toggle_favorite(recipe_id: int):
    db = get_db()
    row = db.execute("SELECT is_favorite FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
    if not row:
        return jsonify({"error": "Recipe not found"}), 404
    next_value = 0 if row["is_favorite"] else 1
    db.execute("UPDATE recipes SET is_favorite = ? WHERE id = ?", (next_value, recipe_id))
    db.commit()
    return jsonify({"recipe_id": recipe_id, "is_favorite": bool(next_value)})


@favorites_api.route("/api/favorites", methods=["GET"])
def get_favorites():
    db = get_db()
    rows = db.execute("SELECT * FROM recipes WHERE is_favorite = 1 ORDER BY created_at DESC").fetchall()
    return jsonify([parse_recipe_row(row) for row in rows])

