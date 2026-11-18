"""Render one selected result without retaining overlays for the entire dataset."""
import hashlib
from core.detector import detect, read_image
from core.exporter import draw_overlay, png_bytes


def comparison_images(data, config, expected_count, expected_sha):
    if hashlib.sha256(data).hexdigest() != expected_sha:
        raise ValueError("사진이 분석 후 변경되었습니다. 다시 분석하세요.")
    original = read_image(data)
    result = detect(original, config)
    if result['count'] != expected_count:
        raise ValueError("표시할 결과가 기존 분석과 다릅니다. 다시 분석하세요.")
    return png_bytes(original), png_bytes(draw_overlay(original, result['cells'], result['uncertain']))
