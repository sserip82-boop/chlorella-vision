import io
import zipfile
from pathlib import Path
import pytest
from PIL import Image, ImageDraw
from core.annotations import parse_yolo
from core.batch import analyze_batch, batch_csv, zip_inputs
from core.detector import Config, detect


@pytest.fixture
def image():
    im = Image.new("RGB", (640,640), "white")
    ImageDraw.Draw(im).ellipse((100,100,120,120), fill=(40,150,40))
    out = io.BytesIO(); im.save(out, format="PNG")
    return out.getvalue()


LABEL = b"0 0.17 0.17 0.04 0.04\n1 0.5 0.5 0.1 0.1"


def test_pair_and_exclude_cluster(image):
    rows = analyze_batch([("A.png", image), ("a.TXT", LABEL)], Config(mode="green"))
    assert rows[0]["ground_truth_count"] == 1
    assert rows[0]["cluster_annotations"] == 1
    assert rows[0]["auto_count"] == 1
    assert rows[0]["percentage_error"] == 0


@pytest.mark.parametrize("label", [b"", b"2 .5 .5 .1 .1", b"0 .5 .5 0 .1", b"0 nan .5 .1 .1", b"0 .99 .5 .1 .1", b"-1 .5 .5 .1 .1", b"0 .5 .5 .1", b"0 .5 .5 .1 .1\n0 .5 .5 .1 .1", b"\xff"])
def test_invalid_label_never_produces_truth(image, label):
    row = analyze_batch([("a.png",image),("a.txt",label)])[0]
    assert row["status"] == "error"
    assert row["ground_truth_count"] is None
    assert row["percentage_error"] is None


@pytest.mark.parametrize("kind", ["missing", "duplicate_label", "duplicate_image", "corrupt", "wrong_size"])
def test_pair_errors(image,kind):
    files = [("a.png", image), ("a.txt", LABEL)]
    if kind == "missing": files.pop()
    if kind == "duplicate_label": files.append(("bbs/a.txt", LABEL))
    if kind == "duplicate_image": files.append(("images/a.png", image))
    if kind == "corrupt": files[0] = ("a.png", b"broken")
    if kind == "wrong_size":
        b = io.BytesIO(); Image.new("RGB",(100,100)).save(b, format="PNG"); files[0] = ("a.png",b.getvalue())
    assert analyze_batch(files)[0]["status"] == "error"


def test_zero_truth_and_orphan(image):
    rows=analyze_batch([("a.png",image),("a.txt",b"1 .5 .5 .1 .1"),("b.txt",LABEL)])
    assert rows[0]["ground_truth_count"] == 0
    assert rows[0]["percentage_error"] is None
    assert rows[1]["status"] == "error"


def test_batch_size_and_limit(image):
    files=[(f"{i}.{ext}", image if ext=="png" else LABEL) for i in range(10) for ext in ("png","txt")]
    assert len(analyze_batch(files)) == 10
    assert len(analyze_batch(files+[("11.png",image),("11.txt",LABEL)]))==11
    with pytest.raises(ValueError): analyze_batch([(f"{i}.png",image) for i in range(465)])
    with pytest.raises(ValueError): analyze_batch([])
    with pytest.raises(ValueError): analyze_batch([("clusters/images/a.png",image)])


def test_zip_and_csv(image):
    out=io.BytesIO()
    with zipfile.ZipFile(out,"w") as z:
        z.writestr("dataset/distinct/images/a.png",image)
        z.writestr("dataset/distinct/bbs/a.txt",LABEL)
        z.writestr("dataset/clusters/images/a.png",image)
    files=zip_inputs(out.getvalue())
    assert len(files)==2
    assert analyze_batch(files)[0]["status"]=="ok"
    data=batch_csv([{"name":"=1+1", "message":"한국어"}])
    assert data.startswith(b"\xef\xbb\xbf")
    assert "'=1+1" in data.decode("utf-8-sig")


def test_real_ten():
    root=Path("data/cidacc/distinct")
    names={p.stem for p in sorted((root/'images').glob('*.png'))[:10]}
    files=[(p.as_posix(),p.read_bytes()) for sub in ("images","bbs") for p in (root/sub).glob("*") if p.stem in names]
    rows=analyze_batch(files)
    assert len(rows)==10 and all(r["status"]=="ok" for r in rows)
    assert [r["ground_truth_count"] for r in rows]==[2,6,6,2,7,26,8,2,4,1]
    for row in rows:
        im=Image.open(row["image_name"])
        assert row["auto_count"]==detect(im,Config())["count"]
