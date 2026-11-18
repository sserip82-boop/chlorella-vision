"""Extract reproducible paired distinct samples without arbitrary ZIP extraction."""
import argparse
import csv
from pathlib import Path, PurePosixPath
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.batch import zip_inputs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--output", type=Path, default=Path("sample_cidacc"))
    parser.add_argument("--count", type=int, default=10)
    args = parser.parse_args()
    if not 1 <= args.count <= 10:
        parser.error("count는 1~10이어야 합니다.")
    files = zip_inputs(args.zip_path.read_bytes())
    images = sorted((n,b) for n,b in files if PurePosixPath(n).suffix.lower() == ".png")[:args.count]
    selected = {PurePosixPath(n).stem for n,_ in images}
    for name, data in files:
        p = PurePosixPath(name)
        if p.stem not in selected:
            continue
        out = args.output / "distinct" / p.parts[-2] / p.name
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.exists() and out.read_bytes() != data:
            raise ValueError(f"기존 파일이 다릅니다. 새 출력 폴더를 선택하세요: {out}")
        out.write_bytes(data)
    print(f"{len(images)}장과 대응 TXT 준비: {args.output}")


if __name__ == "__main__":
    main()
