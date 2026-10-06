import os

import yaml

from .extensions import db
from .models import Category


def _normalize_segment(name, start, completion):
    start = dict(start or {})
    start.setdefault("kind", "warp")
    start.setdefault("spawn", 0)
    start.setdefault("room", 0)
    start.setdefault("layer", -1)
    start.setdefault("snapshot", "")
    
    return {"name": name, "start": start, "completion": dict(completion or {})}


def normalize(definition):
    name = definition.get("name", definition["id"])
    if "segments" in definition:
        segments = [
            _normalize_segment(segment.get("name", name), segment.get("start"), segment.get("completion"))
            for segment in definition["segments"]
        ]
    else:
        segments = [_normalize_segment(name, definition.get("start"), definition.get("completion"))]
    
    return {
        "id": definition["id"],
        "name": name,
        "group": definition.get("group", "Other"),
        "fail_on_death": bool(definition.get("fail_on_death", False)),
        "form": definition.get("form", "choice"),
        "segments": segments,
    }


def load_definitions(index_path):
    base = os.path.dirname(os.path.abspath(index_path))
    with open(index_path, "r", encoding="utf-8") as handle:
        index = yaml.safe_load(handle) or {}

    definitions = []
    for relative in index.get("categories", []):
        with open(os.path.join(base, relative), "r", encoding="utf-8") as handle:
            definitions.append(normalize(yaml.safe_load(handle) or {}))

    return definitions


def sync_categories(path):
    definitions = load_definitions(path)
    seen = set()
    for order, definition in enumerate(definitions):
        category = db.session.get(Category, definition["id"])

        if category is None:
            category = Category(id=definition["id"], config={})
            db.session.add(category)

        category.name = definition["name"]
        category.group_name = definition["group"]
        category.config = {
            "segments": definition["segments"],
            "fail_on_death": definition["fail_on_death"],
            "form": definition["form"],
        }
        category.sort_order = order
        category.active = True

        snapshot = next(
            (segment["start"].get("snapshot") for segment in definition["segments"]
             if segment["start"].get("snapshot")),
            None,
        )

        if snapshot and not category.start_state_hash:
            category.start_state_hash = snapshot

        seen.add(category.id)

    for category in Category.query.all():
        if category.id not in seen:
            category.active = False

    db.session.commit()
    return len(seen)
