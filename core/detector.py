"""Deterministic, non-ML image-processing baseline for chlorella candidates.

Not a trained AI model. Candidate counts are not biological concentration.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Literal
import cv2
import numpy as np
from PIL import Image, ImageOps

Mode = Literal["auto", "green", "gray"]


@dataclass(frozen=True)
class Config:
    mode: Mode = "auto"
    sensitivity: int = 50
    min_area: int = 18
    max_area: int = 2200
    algorithm_version: str = "opencv-baseline-0.1"

    def __post_init__(self):
        if self.mode not in ("auto", "green", "gray"):
            raise ValueError("Unknown image mode")
        if not 0 <= self.sensitivity <= 100:
            raise ValueError("Sensitivity must be between 0 and 100")
        if self.min_area < 1 or self.max_area < self.min_area:
            raise ValueError("Invalid component area limits")


@dataclass(frozen=True)
class Candidate:
    id: str
    x: int
    y: int
    area_px: float
    radius_px: int
    circularity: float
    kind: str = "cell"

    def to_dict(self):
        return asdict(self)


def read_image(data: bytes) -> Image.Image:
    import io
    with Image.open(io.BytesIO(data)) as im:
        im = ImageOps.exif_transpose(im)
        if im.width < 16 or im.height < 16:
            raise ValueError("이미지 가로·세로가 16픽셀 이상이어야 합니다.")
        if im.width * im.height > 25_000_000:
            raise ValueError("이미지가 너무 큽니다. 2,500만 픽셀 이하 이미지를 사용하세요.")
        return im.convert("RGB").copy()


def _green_mask(rgb: np.ndarray, sensitivity: int) -> np.ndarray:
    """Segment relatively saturated green pixels; tolerant of varied illumination."""
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    # broad green hue, relaxed saturation at higher sensitivity
    sat_min = int(np.interp(sensitivity, [0, 100], [75, 15]))
    val_min = int(np.interp(sensitivity, [0, 100], [40, 15]))
    lo = np.array([28, sat_min, val_min], np.uint8)
    hi = np.array([105, 255, 255], np.uint8)
    mask = cv2.inRange(hsv, lo, hi)
    return mask


def _gray_mask(rgb: np.ndarray, sensitivity: int) -> np.ndarray:
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    eq = cv2.createCLAHE(clipLimit=1.8, tileGridSize=(8, 8)).apply(gray)
    blur = cv2.GaussianBlur(eq, (3, 3), 0)
    # darker-than-neighbor candidates; C lower at higher sensitivity
    c = int(np.interp(sensitivity, [0, 100], [14, 1]))
    block_size = 31 if min(rgb.shape[:2]) >= 31 else 15
    local = cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                  cv2.THRESH_BINARY_INV, block_size, c)
    return local


def _clean_mask(mask: np.ndarray) -> np.ndarray:
    mask = cv2.medianBlur(mask, 3)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    return cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)


def detect(pil_img: Image.Image, config: Config) -> dict:
    """Return detected candidates and uncertain large/irregular regions (not counted)."""
    rgb = np.asarray(pil_img.convert("RGB"), dtype=np.uint8)
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    green_fraction = float(np.mean((hsv[:, :, 0] >= 28) &
                                   (hsv[:, :, 0] <= 105) &
                                   (hsv[:, :, 1] >= 45)))
    used_mode = config.mode
    if used_mode == "auto":
        used_mode = "green" if green_fraction >= 0.018 else "gray"
    raw_mask = _green_mask(rgb, config.sensitivity) if used_mode == "green" else _gray_mask(rgb, config.sensitivity)
    mask = _clean_mask(raw_mask)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cells, uncertain = [], []
    # sort by center to make IDs deterministic, independent of contour enumeration
    ordered = sorted(contours, key=lambda c: (cv2.boundingRect(c)[1], cv2.boundingRect(c)[0]))
    for i, cnt in enumerate(ordered):
        area = float(cv2.contourArea(cnt))
        if area < config.min_area:
            continue
        perimeter = float(cv2.arcLength(cnt, True))
        if perimeter <= 0:
            continue
        x, y, w, h = cv2.boundingRect(cnt)
        circularity = float(min(1, 4 * np.pi * area / (perimeter ** 2)))
        aspect = w / max(1, h)
        moments = cv2.moments(cnt)
        if abs(moments["m00"]) > 1e-9:
            cx = int(round(moments["m10"] / moments["m00"]))
            cy = int(round(moments["m01"] / moments["m00"]))
        else:
            cx, cy = x + w // 2, y + h // 2
        radius = int(max(4, np.sqrt(area / np.pi)))
        # Avoid treating obvious merged blobs as single validated cells.
        is_suspect = (area > config.max_area or circularity < 0.32 or
                      aspect < 0.38 or aspect > 2.6)
        item = Candidate(id=f"C{i:04d}", x=cx, y=cy, area_px=round(area, 1),
                         radius_px=radius, circularity=round(circularity, 3),
                         kind="uncertain" if is_suspect else "cell")
        (uncertain if is_suspect else cells).append(item.to_dict())
    return {"cells": cells, "uncertain": uncertain, "count": len(cells),
            "used_mode": used_mode, "green_fraction": round(green_fraction, 4),
            "mask": mask, "config": asdict(config)}
