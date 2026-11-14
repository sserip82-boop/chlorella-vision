"""Error metrics. 'manual' must be independent of automatic markers."""
from __future__ import annotations


def error_metrics(automatic: int, manual: int | None) -> dict:
    if manual is None:
        return {"absolute_error": None, "percentage_error": None}
    if automatic < 0 or manual < 0:
        raise ValueError("Counts cannot be negative")
    absolute = abs(automatic - manual)
    return {"absolute_error": absolute,
            "percentage_error": round(100 * absolute / manual, 2) if manual else None}


def mae(pairs: list[tuple[int, int]]) -> float | None:
    if not pairs:
        return None
    if any(a < 0 or b < 0 for a, b in pairs):
        raise ValueError("Counts cannot be negative")
    return round(sum(abs(a - b) for a, b in pairs) / len(pairs), 3)
