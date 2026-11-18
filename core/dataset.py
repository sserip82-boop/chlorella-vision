"""Read the versioned, attributed CIDACC dataset bundled with the application."""
import hashlib
import json
from pathlib import Path

DATA_ROOT = Path(__file__).resolve().parents[1] / "data" / "cidacc"
GROUP_COUNTS = {"distinct": 464, "clusters": 164}


def bundled_files(group="distinct", root=DATA_ROOT):
    """Verify file integrity before returning encoded images and matching labels."""
    if group not in GROUP_COUNTS:
        raise ValueError("알 수 없는 CIDACC 사진 종류입니다.")
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    entries = {e["path"]: e for e in manifest["files"]}
    files = []
    names = sorted(p.name for p in (root / group / "images").glob("*.png"))
    if len(names) != GROUP_COUNTS[group]:
        raise ValueError("준비된 CIDACC 사진이 누락되었습니다. 설치 파일을 확인하세요.")
    for name in names:
        for sub, filename in (("images", name), ("bbs", Path(name).stem + ".txt")):
            relative = f"{group}/{sub}/{filename}"
            data = (root / relative).read_bytes()
            expected = entries.get(relative)
            if expected is None or len(data) != expected["bytes"] or hashlib.sha256(data).hexdigest() != expected["sha256"]:
                raise ValueError(f"기본 데이터가 변경되었거나 손상되었습니다: {relative}")
            files.append((relative, data))
    return files
