
from flask import Blueprint, abort, current_app, jsonify, request

from .extensions import db
from .models import Category, Run, best_runs_query, rank_for_run

api_bp = Blueprint("api", __name__)


@api_bp.errorhandler(404)
def not_found(_error):
    return jsonify({"error": "not found"}), 404


@api_bp.get("/categories")
def categories():
    rows = Category.query.filter_by(active=True).order_by(Category.sort_order).all()
    return jsonify({"categories": [category.to_dict() for category in rows]})


def requested_limit():
    try:
        limit = int(request.args.get("limit", 50))
    except ValueError:
        return None
    return max(1, min(limit, current_app.config["LEADERBOARD_LIMIT"]))


def board_payload(category, limit, user):
    runs = best_runs_query(category.id, limit).all()
    payload = {
        "category": category.to_dict(),
        "entries": [run.to_dict(rank=index + 1) for index, run in enumerate(runs)],
    }
    if user is not None:
        best = (
            Run.query.filter_by(user_id=user.id, category_id=category.id, status="accepted")
            .order_by(Run.rta_ms.asc(), Run.submitted_at.asc())
            .first()
        )
        if best is not None:
            payload["me"] = best.to_dict(rank=rank_for_run(best))
    return payload


@api_bp.get("/categories/<category_id>/leaderboard")
def leaderboard(category_id):
    category = db.session.get(Category, category_id)
    if category is None:
        abort(404)
    limit = requested_limit()
    if limit is None:
        return jsonify({"error": "invalid limit"}), 400
    return jsonify(board_payload(category, limit, None))


@api_bp.get("/leaderboards")
def leaderboards():
    limit = requested_limit()
    if limit is None:
        return jsonify({"error": "invalid limit"}), 400
    rows = Category.query.filter_by(active=True).order_by(Category.sort_order).all()
    return jsonify({"boards": {category.id: board_payload(category, limit, None) for category in rows}})
