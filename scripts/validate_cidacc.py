"""Run the same V2 validation outside Streamlit and export a CSV."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.batch import analyze_batch, batch_csv


def main():
    p = argparse.ArgumentParser()
    p.add_argument("folder", type=Path, help="distinct 폴더 (images/와 bbs/ 포함)")
    p.add_argument("--output", type=Path, default=Path("validation.csv"))
    args = p.parse_args()
    files = [(f.as_posix(), f.read_bytes()) for sub in ("images", "bbs") for f in sorted((args.folder/sub).glob("*")) if f.is_file()]
    rows = analyze_batch(files)
    args.output.write_bytes(batch_csv(rows))
    good = [r for r in rows if r["status"] == "ok"]
    print(f"정상 {len(good)} / 전체 {len(rows)}; CSV: {args.output}")
    if good:
        print("MAE:", sum(r["absolute_error"] for r in good)/len(good))
    if len(good) != len(rows):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
