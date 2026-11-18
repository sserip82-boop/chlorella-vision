"""CIDACC distinct annotation validation. Reuses the unchanged V1 detector."""
from __future__ import annotations
import csv
import hashlib
import io
from pathlib import PurePosixPath
import zipfile

from core.annotations import parse_yolo
from core.detector import Config, detect, read_image
from core.metrics import error_metrics

CLASS_EVIDENCE = "CIDACC-13219972-audit-2026-11-18"
CELL_CLASS = 0
CLUSTER_CLASS = 1
MAX_FILE = 10 * 1024 * 1024


def zip_inputs(data: bytes) -> list[tuple[str, bytes]]:
    """Read only distinct images/bbs; never extract archive paths to disk."""
    result = []
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for info in archive.infolist():
            p = PurePosixPath(info.filename)
            if info.is_dir() or len(p.parts) < 3:
                continue
            if p.parts[-3:-1] not in (("distinct", "images"), ("distinct", "bbs")):
                continue
            if ".." in p.parts or p.is_absolute() or "\\" in info.filename:
                raise ValueError("ZIP 경로가 잘못되었습니다.")
            if p.suffix.lower() not in (".png", ".txt"):
                continue
            if info.file_size > MAX_FILE:
                raise ValueError(f"파일이 10MB를 초과합니다: {p.name}")
            if len(result) >= 2000 or sum(len(b) for _, b in result)+info.file_size > 100*1024*1024:
                raise ValueError("ZIP에서 읽는 데이터는 최대 100MB / 2,000개 파일입니다.")
            result.append((info.filename, archive.read(info)))
    if not result:
        raise ValueError("distinct/images/*.png와 distinct/bbs/*.txt가 필요합니다.")
    return result


def analyze_batch(files: list[tuple[str, bytes]], config: Config = Config()) -> list[dict]:
    images, labels = {}, {}
    for name, data in files:
        p = PurePosixPath(name.replace("\\", "/"))
        if "clusters" in p.parts or "original_images" in p.parts:
            raise ValueError("distinct의 640×640 이미지와 bbs TXT만 사용하세요.")
        target = images if p.suffix.lower() in (".png", ".jpg", ".jpeg") else labels if p.suffix.lower() == ".txt" else None
        if target is not None:
            target.setdefault(p.stem.casefold(), []).append((name, data))
    if not 1 <= len(images) <= 10:
        raise ValueError("이미지는 1~10장이어야 합니다. 10장을 선택해 주세요.")
    rows = []
    for stem, entries in sorted(images.items()):
        name, data = entries[0]
        row = dict(image_name=name, image_sha256=hashlib.sha256(data).hexdigest(),
                   annotation_name=None, annotation_sha256=None, auto_count=None,
                   ground_truth_count=None, cluster_annotations=None, uncertain_regions=None,
                   absolute_error=None, percentage_error=None, status="error", message="",
                   class_evidence=CLASS_EVIDENCE, **config.__dict__)
        try:
            if len(entries) != 1:
                raise ValueError("같은 이름의 이미지가 중복되었습니다.")
            matches = labels.get(stem, [])
            if len(matches) != 1:
                raise ValueError("동일 파일명의 bbs TXT가 없거나 중복되었습니다.")
            ann_name, ann = matches[0]
            row.update(annotation_name=ann_name, annotation_sha256=hashlib.sha256(ann).hexdigest())
            if max(len(data), len(ann)) > MAX_FILE:
                raise ValueError("이미지/TXT는 각각 10MB 이하여야 합니다.")
            image = read_image(data)
            if image.size != (640, 640):
                raise ValueError("CIDACC distinct 이미지는 640×640이어야 합니다. 원본 사진은 제외하세요.")
            items = parse_yolo(ann.decode("utf-8-sig"))
            if not items:
                raise ValueError("빈 TXT는 누락 주석과 구별할 수 없어 정답 계산을 중단했습니다.")
            unknown = {i["class_id"] for i in items} - {CELL_CLASS, CLUSTER_CLASS}
            if unknown:
                raise ValueError(f"의미가 확인되지 않은 클래스: {sorted(unknown)}")
            truth = sum(i["class_id"] == CELL_CLASS for i in items)
            result = detect(image, config)
            row.update(auto_count=result["count"], ground_truth_count=truth,
                       cluster_annotations=sum(i["class_id"] == CLUSTER_CLASS for i in items),
                       uncertain_regions=len(result["uncertain"]), mode_used=result["used_mode"],
                       **error_metrics(result["count"], truth), status="ok",
                       message="정답 0개: 백분율오차 계산 불가" if truth == 0 else "")
        except (ValueError, OSError, UnicodeError) as exc:
            row["message"] = str(exc)
        rows.append(row)
    # Surface orphan labels rather than silently discarding them.
    for stem in sorted(labels.keys() - images.keys()):
        rows.append(dict(image_name="", annotation_name=labels[stem][0][0], status="error",
                         message="대응 이미지가 없는 TXT입니다."))
    return rows


def batch_csv(rows: list[dict]) -> bytes:
    fields = list(dict.fromkeys(key for row in rows for key in row))
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    # Avoid spreadsheet formula execution from uploaded file names/messages.
    writer.writerows({k: "'"+v if isinstance(v, str) and v.lstrip().startswith(("=", "+", "-", "@")) else v
                     for k, v in row.items()} for row in rows)
    return output.getvalue().encode("utf-8-sig")
