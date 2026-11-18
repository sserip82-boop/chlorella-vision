"""Render one selected result without retaining overlays for the entire dataset."""
import hashlib
from core.detector import detect, read_image
from core.exporter import draw_overlay, png_bytes
from core.annotations import parse_yolo
from PIL import ImageDraw


def reference_image(data, annotation, expected_count):
    items = parse_yolo(annotation.decode('utf-8-sig'))
    cells = [i for i in items if i['class_id'] == 0]
    if len(cells) != expected_count or any(i['class_id'] not in (0, 1) for i in items):
        raise ValueError('정답 표시가 분석 결과와 다릅니다. 다시 분석하세요.')
    image = read_image(data)
    draw = ImageDraw.Draw(image)
    for cell in cells:
        x,y,w,h = [cell[k] for k in ('cx_norm','cy_norm','w_norm','h_norm')]
        draw.rectangle(((x-w/2)*image.width,(y-h/2)*image.height,
                        (x+w/2)*image.width,(y+h/2)*image.height), outline='#2999ff', width=3)
    return png_bytes(image)


def comparison_images(data, config, expected_count, expected_sha):
    if hashlib.sha256(data).hexdigest() != expected_sha:
        raise ValueError("사진이 분석 후 변경되었습니다. 다시 분석하세요.")
    original = read_image(data)
    result = detect(original, config)
    if result['count'] != expected_count:
        raise ValueError("표시할 결과가 기존 분석과 다릅니다. 다시 분석하세요.")
    return png_bytes(original), png_bytes(draw_overlay(original, result['cells'], result['uncertain']))
