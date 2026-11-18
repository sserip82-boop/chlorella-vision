from pathlib import Path
from PIL import Image
from core.detector import detect, Config
from core.editor import new_edits, add_missing_point, delete_nearest, corrected_count, undo
from core.metrics import error_metrics
from streamlit.testing.v1 import AppTest


def test_demo_detector_and_editor():
    for name in ("demo_gray.png", "demo_green.png"):
        result=detect(Image.open(Path("examples")/name),Config())
        assert result["count"]==18
        assert len(result["uncertain"])==1
        edits=new_edits(); cell=result["cells"][0]
        assert delete_nearest(edits,result["cells"],cell["x"],cell["y"])
        assert corrected_count(18,edits)==17
        assert undo(edits) and corrected_count(18,edits)==18
        assert not add_missing_point(edits,result["cells"],cell["x"],cell["y"])
    assert error_metrics(5,4)=={"absolute_error":1,"percentage_error":25.0}


def test_v1_and_v2_screen():
    at=AppTest.from_file(Path("app.py").resolve(), default_timeout=20).run()
    assert not at.exception
    at.sidebar.radio[0].set_value("V1 · 한 장 분석·수동 검증").run()
    at.sidebar.radio[1].set_value("합성 데모 이미지").run()
    assert not at.exception
    button=next(b for b in at.button if "이미지 자동 분석 실행" in b.label)
    button.click().run()
    assert not at.exception
    assert at.session_state["analysis"]["data"]["count"]==18
    at.sidebar.radio[0].set_value("V2 · CIDACC 일괄 검증").run()
    assert not at.exception
    assert any("분석 시작" in b.label for b in at.button)


def test_batch_ui_real_inputs():
    # AppTest does not drive file uploads; provide real upload bytes at that boundary.
    script = '''
from pathlib import Path
import streamlit as st
from core.batch_ui import render_batch
class Upload:
    def __init__(self,p): self.name=p.name; self.p=p
    def getvalue(self): return self.p.read_bytes()
root=Path('data/cidacc/distinct')
names={p.stem for p in sorted((root/'images').glob('*.png'))[:10]}
st.file_uploader=lambda *a,**k: [Upload(p) for sub in ('images','bbs') for p in sorted((root/sub).glob('*')) if p.stem in names]
render_batch()
'''
    at=AppTest.from_string(script,default_timeout=20).run()
    at.radio[0].set_value("이미지와 TXT 함께 업로드").run()
    at.button[0].click().run()
    assert not at.exception
    assert len(at.dataframe[0].value)==10
    assert len(at.get("download_button"))==2
    assert next(m for m in at.metric if m.label=='평균 개수 차이(MAE)').value=="32.6"
    assert len(at.get('image'))==2
    at.slider[0].set_value(51).run()
    assert not at.exception
    assert not at.dataframe


def test_bundled_full_dataset_ready_without_upload():
    at=AppTest.from_file(Path("app.py").resolve(), default_timeout=60).run()
    at.sidebar.radio[0].set_value("V2 · CIDACC 일괄 검증").run()
    assert not at.exception
    assert not at.get("file_uploader")
    button=next(b for b in at.button if '분석 시작' in b.label)
    assert not button.disabled
    button.click().run()
    assert not at.exception
    assert len(at.dataframe[0].value)==464
    assert next(m for m in at.metric if m.label=='평균 개수 차이(MAE)').value=="15.058"
    assert len(at.get("download_button"))==2
    assert len(at.get('image'))==2
    picker=next(s for s in at.selectbox if s.label=='확인할 사진')
    picker.set_value(2).run()
    assert not at.exception
    assert at.metric[0].value=='13개'
    error_index=next(i for i,r in enumerate(at.session_state['batch_result'][1]) if r['image_name'].endswith('/335.png'))
    next(s for s in at.selectbox if s.label=='확인할 사진').set_value(error_index).run()
    assert not at.exception
    assert len(at.get('image'))==1
    assert len(at.get('download_button'))==1
    next(r for r in at.radio if r.label=="사진 종류").set_value("뭉친 세포 · 164장").run()
    assert not at.exception
    assert not at.dataframe
    assert not at.get("download_button")
    assert not at.button
    assert any("개별 세포 정답 개수" in w.value for w in at.warning)
