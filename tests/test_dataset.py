import json
from pathlib import Path
import pytest
from core.batch import analyze_batch, batch_csv
from core.dataset import DATA_ROOT, bundled_files


def test_full_dataset_integrity_and_pairing():
    # SHA-256 verification runs for every image/TXT on both groups.
    for group, count in (("distinct",464),("clusters",164)):
        files=bundled_files(group)
        assert len(files)==count*2
        assert {Path(n).stem for n,_ in files if n.endswith('.png')}=={Path(n).stem for n,_ in files if n.endswith('.txt')}
    assert len(json.loads((DATA_ROOT/'manifest.json').read_text())['files'])==1256


def test_all_distinct_results_and_progress():
    calls=[]
    rows=analyze_batch(bundled_files(), progress=lambda done,total:calls.append((done,total)))
    assert len(rows)==464
    assert calls[0]==(1,464) and calls[-1]==(464,464)
    good=[r for r in rows if r['status']=='ok']
    errors=[r for r in rows if r['status']=='error']
    assert len(good)==462
    assert {Path(r['image_name']).name for r in errors}=={'335.png','515.png'}
    assert all(r['ground_truth_count'] is None and r['percentage_error'] is None for r in errors)
    assert sum(r['ground_truth_count'] for r in good)==2732
    assert len(batch_csv(rows).decode('utf-8-sig').splitlines())==465


def test_damaged_bundled_file_rejected(tmp_path,monkeypatch):
    from core import dataset
    monkeypatch.setitem(dataset.GROUP_COUNTS,'distinct',1)
    image=tmp_path/'distinct/images/1.png'; image.parent.mkdir(parents=True); image.write_bytes(b'changed')
    (tmp_path/'manifest.json').write_text(json.dumps({'files':[{'path':'distinct/images/1.png','bytes':3,'sha256':'invalid'}]}))
    with pytest.raises(ValueError,match='손상'):
        bundled_files(root=tmp_path)
