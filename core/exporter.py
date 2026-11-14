"""Create annotated PNG and Excel-friendly CSV, without persistent storage."""
from __future__ import annotations
import csv
import io
from PIL import Image, ImageDraw


def draw_overlay(image: Image.Image, cells: list[dict], uncertain: list[dict] | None = None,
                 deleted: list[str] | None = None, added: list[dict] | None = None,
                 manual: list[dict] | None = None, show_auto: bool = True) -> Image.Image:
    out = image.convert("RGB").copy()
    draw = ImageDraw.Draw(out)
    deleted_ids = set(deleted or [])
    if show_auto:
        for c in cells:
            x, y, r = c["x"], c["y"], c["radius_px"] + 3
            color = "#d63043" if c["id"] in deleted_ids else "#0bd081"
            draw.ellipse((x-r, y-r, x+r, y+r), outline=color, width=3)
            if c["id"] in deleted_ids:
                draw.line((x-r, y-r, x+r, y+r), fill=color, width=2)
        for c in (uncertain or []):
            x, y, r = c["x"], c["y"], c["radius_px"] + 5
            draw.ellipse((x-r, y-r, x+r, y+r), outline="#f59d26", width=3)
        for p in (added or []):
            x, y = p["x"], p["y"]
            draw.ellipse((x-8, y-8, x+8, y+8), outline="#2f7cf6", width=3)
            draw.line((x-5, y, x+5, y), fill="#2f7cf6", width=2)
            draw.line((x, y-5, x, y+5), fill="#2f7cf6", width=2)
    else:
        for p in (manual or []):
            x, y = p["x"], p["y"]
            draw.ellipse((x-7, y-7, x+7, y+7), outline="#2f7cf6", width=3)
    return out


def png_bytes(image: Image.Image) -> bytes:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def csv_bytes(rows: list[dict]) -> bytes:
    if not rows:
        return b""
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()), extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8-sig")


def make_annotated_png(image: Image.Image, cells: list[dict], uncertain: list[dict],
                       edits: dict, summary: str) -> bytes:
    annotated = draw_overlay(image, cells, uncertain, edits["deleted"], edits["added"])
    footer = 34
    report = Image.new("RGB", (annotated.width, annotated.height + footer), "#f4f9f5")
    report.paste(annotated, (0, 0))
    draw = ImageDraw.Draw(report)
    draw.text((10, annotated.height + 9), summary, fill="#123e2b")
    return png_bytes(report)
