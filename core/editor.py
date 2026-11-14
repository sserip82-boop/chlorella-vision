"""Click-edit model and coordinate conversions, independent of Streamlit."""
from __future__ import annotations
from copy import deepcopy
import math


def new_edits() -> dict:
    return {"deleted": [], "added": [], "history": []}


def to_original_coords(click_x: float, click_y: float, displayed_size: tuple[int, int], original_size: tuple[int, int]):
    dw, dh = displayed_size
    ow, oh = original_size
    if min(dw, dh, ow, oh) <= 0:
        raise ValueError("Image sizes must be positive")
    x = min(ow - 1, max(0, round(click_x * ow / dw)))
    y = min(oh - 1, max(0, round(click_y * oh / dh)))
    return x, y


def add_point(edits: dict, x: int, y: int, radius: int = 8) -> bool:
    if any(math.dist((x, y), (p["x"], p["y"])) <= max(3, radius // 2)
           for p in edits["added"]):
        return False
    edits["history"].append(deepcopy((edits["deleted"], edits["added"])))
    edits["added"].append({"x": x, "y": y})
    return True


def delete_nearest(edits: dict, cells: list[dict], x: int, y: int, max_distance: int = 18) -> bool:
    alive = [c for c in cells if c["id"] not in edits["deleted"]]
    if not alive:
        return False
    nearest = min(alive, key=lambda c: math.dist((x, y), (c["x"], c["y"])))
    d = math.dist((x, y), (nearest["x"], nearest["y"]))
    if d > max(max_distance, nearest["radius_px"] + 5):
        return False
    edits["history"].append(deepcopy((edits["deleted"], edits["added"])))
    edits["deleted"].append(nearest["id"])
    return True


def remove_nearest_manual(points: list[dict], x: int, y: int, threshold: int = 18) -> bool:
    if not points:
        return False
    index = min(range(len(points)), key=lambda i: math.dist((x, y), (points[i]["x"], points[i]["y"])))
    if math.dist((x, y), (points[index]["x"], points[index]["y"])) > threshold:
        return False
    points.pop(index)
    return True


def undo(edits: dict) -> bool:
    if not edits["history"]:
        return False
    edits["deleted"], edits["added"] = edits["history"].pop()
    return True


def corrected_count(auto_count: int, edits: dict) -> int:
    return auto_count - len(edits["deleted"]) + len(edits["added"])


def add_missing_point(edits: dict, cells: list[dict], x: int, y: int, radius: int = 8) -> bool:
    """Prevent duplicate manual addition on an already-counted automatic cell."""
    for c in cells:
        if c["id"] not in edits["deleted"] and math.dist((x, y), (c["x"], c["y"])) <= max(radius, c["radius_px"] + 2):
            return False
    return add_point(edits, x, y, radius)
