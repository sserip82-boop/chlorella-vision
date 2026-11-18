"""CIDACC/YOLO bbox parser; class labels are NOT assumed to equal cells.

Choose the proper cell class after reviewing labels and the dataset metadata.
"""
from __future__ import annotations


def parse_yolo(text: str) -> list[dict]:
    items = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        cols = line.split()
        if len(cols) != 5:
            raise ValueError(f"Invalid bbox at line {lineno}")
        try:
            cls = int(cols[0])
            x, y, w, h = map(float, cols[1:])
        except ValueError as e:
            raise ValueError(f"Invalid values at line {lineno}") from e
        if cls < 0 or not all(0 <= v <= 1 for v in (x, y, w, h)):
            raise ValueError(f"Out-of-range YOLO coordinates at line {lineno}")
        if w <= 0 or h <= 0:
            raise ValueError(f"Empty bbox at line {lineno}")
        # Allow floating-point rounding at image boundaries.
        if x-w/2 < -1e-6 or y-h/2 < -1e-6 or x+w/2 > 1+1e-6 or y+h/2 > 1+1e-6:
            raise ValueError(f"BBox outside image at line {lineno}")
        items.append({"class_id": cls, "cx_norm": x, "cy_norm": y,
                      "w_norm": w, "h_norm": h})
    if len({tuple(item.values()) for item in items}) != len(items):
        raise ValueError("Duplicate bbox annotations")
    return items


def count_class(items: list[dict], cell_class_id: int | None = None) -> int | None:
    if cell_class_id is None:
        return None
    return sum(item["class_id"] == cell_class_id for item in items)
