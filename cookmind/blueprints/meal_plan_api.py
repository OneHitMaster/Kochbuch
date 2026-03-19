from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request

from ..db import get_db

meal_plan_api = Blueprint("meal_plan_api", __name__)

MEAL_SLOTS = ["Frühstück", "Mittag", "Abend", "Snacks"]


def _normalize_payload(payload: Any) -> List[Dict[str, Any]]:
    """
    Accepts multiple formats:
    - {"entries":[{day_index,meal_slot,recipe_id}, ...]}
    - {"assignments":[...]}
    - directly a list of entries
    """
    if payload is None:
        return []
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        if isinstance(payload.get("entries"), list):
            return payload["entries"]
        if isinstance(payload.get("assignments"), list):
            return payload["assignments"]
    return []


def _validate_entry(entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    try:
        day_index = int(entry.get("day_index"))
    except (TypeError, ValueError):
        return None

    meal_slot = (entry.get("meal_slot") or "").strip()
    if meal_slot not in MEAL_SLOTS:
        return None

    # recipe_id can be null to mean "remove assignment"
    recipe_id = entry.get("recipe_id")
    if recipe_id is not None:
        try:
            recipe_id = int(recipe_id)
        except (TypeError, ValueError):
            return None

    if day_index < 0 or day_index > 6:
        return None

    return {"day_index": day_index, "meal_slot": meal_slot, "recipe_id": recipe_id}


@meal_plan_api.route("/api/meal-plan", methods=["GET"])
def get_meal_plan():
    db = get_db()
    rows = db.execute("SELECT day_index, meal_slot, recipe_id FROM meal_plan").fetchall()

    # Create full structure for the client.
    result: List[Dict[str, Any]] = []
    for day_index in range(7):
        day_items: Dict[str, Optional[int]] = {slot: None for slot in MEAL_SLOTS}
        result.append({"day_index": day_index, "items": day_items})

    for row in rows:
        day_index = row["day_index"]
        meal_slot = row["meal_slot"]
        recipe_id = row["recipe_id"]
        for day in result:
            if day["day_index"] == day_index:
                day["items"][meal_slot] = recipe_id
                break

    return jsonify(result)


@meal_plan_api.route("/api/meal-plan", methods=["POST"])
def upsert_meal_plan():
    payload = request.get_json(silent=True)
    entries = _normalize_payload(payload)
    if not entries:
        return jsonify({"error": "No entries provided"}), 400

    db = get_db()
    valid_entries: List[Dict[str, Any]] = []
    for entry in entries:
        v = _validate_entry(entry)
        if v is not None:
            valid_entries.append(v)

    if not valid_entries:
        return jsonify({"error": "No valid entries provided"}), 400

    # Upsert assignments. recipe_id == None means delete.
    for e in valid_entries:
        if e["recipe_id"] is None:
            db.execute(
                "DELETE FROM meal_plan WHERE day_index=? AND meal_slot=?",
                (e["day_index"], e["meal_slot"]),
            )
        else:
            # Ensure recipe exists
            exists = db.execute("SELECT id FROM recipes WHERE id=?", (e["recipe_id"],)).fetchone()
            if not exists:
                return jsonify({"error": f"Recipe not found: {e['recipe_id']}"}), 400

            db.execute(
                """
                INSERT INTO meal_plan(day_index, meal_slot, recipe_id)
                VALUES (?, ?, ?)
                ON CONFLICT(day_index, meal_slot) DO UPDATE SET recipe_id=excluded.recipe_id
                """,
                (e["day_index"], e["meal_slot"], e["recipe_id"]),
            )

    db.commit()
    return jsonify({"ok": True})


@meal_plan_api.route("/api/meal-plan/reset", methods=["POST"])
def reset_meal_plan():
    db = get_db()
    db.execute("DELETE FROM meal_plan")
    db.commit()
    return jsonify({"ok": True})

