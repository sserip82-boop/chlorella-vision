"""Chlorella Vision V1 — educational image-processing baseline.
Run: streamlit run app.py
"""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import io
import json
import hashlib

import pandas as pd
import streamlit as st
from PIL import Image
from streamlit_image_coordinates import streamlit_image_coordinates

from core.detector import Config, detect, read_image
from core.editor import (new_edits, to_original_coords, add_missing_point, delete_nearest,
                         remove_nearest_manual, undo, corrected_count)
from core.exporter import draw_overlay, png_bytes, csv_bytes, make_annotated_png
from core.metrics import error_metrics, mae
from core.identity import image_sha256, analysis_id

ROOT = Path(__file__).parent
st.set_page_config(page_title="Chlorella Vision · 세포 이미지 분석", page_icon="🧫", layout="wide")
st.markdown('''<style>
  .block-container { padding-top: 1.4rem; max-width: 1440px; }
  h1,h2,h3 { letter-spacing: -0.03em; }
  [data-testid="stMetric"] { border: 1px solid rgba(100,140,115,.22);
  border-radius: 12px; padding: 12px; background: rgba(100,180,130,.045); }
  [data-testid="stSidebar"] { background: rgba(90,150,110,.04); }
  .subtle {color:#62786d;font-size:.92rem}
  </style>''', unsafe_allow_html=True)

DEFAULT_STATE = {
    "image_hash": None, "analysis": None, "edits": None,
    "manual_points": [], "manual_history": [], "manual_started": False,
    "manual_finished": False, "manual_blind": None,
    "verified_records": {}, "last_edit_event": None, "last_manual_event": None,
}
for k, val in DEFAULT_STATE.items():
    if k not in st.session_state:
        st.session_state[k] = deepcopy(val)


def reset_image_state(new_hash):
    for key in ("analysis", "edits", "manual_points", "manual_history", "manual_started",
                "manual_finished", "manual_blind", "last_edit_event", "last_manual_event"):
        st.session_state[key] = deepcopy(DEFAULT_STATE[key])
    st.session_state["image_hash"] = new_hash


def display_copy(img, max_width=760):
    if img.width <= max_width:
        return img.copy(), (img.width, img.height)
    width = max_width
    height = max(1, round(img.height * (width / img.width)))
    return img.resize((width, height), Image.Resampling.LANCZOS), (width, height)


def handle_click(value, last_event_key, display_size, original_size):
    """Return original pixel coordinate exactly once per distinct browser click."""
    if not isinstance(value, dict) or "x" not in value or "y" not in value:
        return None
    # Component v0.4.1 includes unix_time. Keep compatibility with older versions.
    timestamp = value.get("unix_time", value.get("timestamp", value.get("time")))
    token = (timestamp, int(value["x"]), int(value["y"]))
    if st.session_state[last_event_key] == token:
        return None
    st.session_state[last_event_key] = token
    return to_original_coords(value["x"], value["y"], display_size, original_size)


def analysis_row(image_name, image_hash, cfg: Config, analysis, edits, manual_count, blind, note=""):
    auto = analysis["count"]
    corrected = corrected_count(auto, edits)
    metrics = error_metrics(auto, manual_count)
    corrected_metrics = error_metrics(corrected, manual_count)
    return {
        "image_name": image_name, "image_sha256": image_hash,
        "analysis_id": analysis_id(image_hash, cfg.__dict__),
        "algorithm_version": cfg.algorithm_version, "mode_requested": cfg.mode,
        "mode_used": analysis["used_mode"], "sensitivity": cfg.sensitivity,
        "min_area_px": cfg.min_area, "max_area_px": cfg.max_area,
        "auto_count": auto, "manual_count": manual_count if manual_count is not None else "",
        "corrected_count": corrected, "deleted_count": len(edits["deleted"]),
        "added_count": len(edits["added"]),
        "absolute_error": metrics["absolute_error"] if metrics["absolute_error"] is not None else "",
        "percentage_error": metrics["percentage_error"] if metrics["percentage_error"] is not None else "",
        "corrected_absolute_error": (corrected_metrics["absolute_error"]
                                    if corrected_metrics["absolute_error"] is not None else ""),
        "manual_count_before_auto": blind if blind is not None else "",
        "uncertain_regions": len(analysis["uncertain"]),
        "note": note.strip(), "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
    }


st.title("🧫 Chlorella Vision")
workflow = st.sidebar.radio("작업 선택", ["V1 · 한 장 분석·수동 검증", "V2 · CIDACC 일괄 검증"], index=1)
if workflow == "V2 · CIDACC 일괄 검증":
    from core.batch_ui import render_batch
    render_batch()
    st.stop()
st.caption("클로렐라 현미경 이미지 자동 계수 · 수동 검증 · 오차 분석")
st.info("**V1은 OpenCV 기반 이미지 처리 도구입니다. 학습형 AI 모델이 아니며, 검출 결과는 사람이 검증해야 합니다.**")

with st.sidebar:
    st.subheader("① 사진 선택")
    src = st.radio("이미지 가져오기", ["파일 업로드", "합성 데모 이미지"],
                   help="합성 데모는 기능 확인용이며 공개 실험 데이터가 아닙니다.")
    data, filename = None, None
    if src == "파일 업로드":
        up = st.file_uploader("현미경 JPG·PNG", type=["jpg", "jpeg", "png"],
                              help="10MB 이하 권장. CIDACC distinct 이미지부터 시작하세요.")
        if up:
            data, filename = up.getvalue(), up.name
            if len(data) > 10*1024*1024:
                st.error("10MB 이하 이미지를 선택하세요.")
                data = None
    else:
        example = st.selectbox("합성 예제", ["demo_green.png", "demo_gray.png"])
        data = (ROOT / "examples" / example).read_bytes()
        filename = "SYNTHETIC_" + example
        st.warning("이 사진은 코드로 생성한 **가상 세포**입니다. 실제 성능 검증에 사용하지 마세요.")

    st.divider()
    st.subheader("② 분석 설정")
    mode_display = st.selectbox("이미지 분석 방식", ["자동 선택", "초록색 이미지", "회색조 이미지"])
    mode = {"자동 선택": "auto", "초록색 이미지": "green", "회색조 이미지": "gray"}[mode_display]
    sensitivity = st.slider("민감도", min_value=0, max_value=100, value=50, step=5)
    min_area = st.slider("최소 후보 면적 (px²)", min_value=5, max_value=500, value=18, step=1)
    max_area = st.slider("최대 후보 면적 (px²)", min_value=100, max_value=10000, value=2200, step=100)
    if max_area < min_area:
        st.error("최대 면적이 최소 면적보다 작습니다.")
    st.caption("민감도·면적값은 연구 데이터에서 직접 조정하고 검증하세요.")
    st.divider()
    st.markdown("**공개 데이터 출처**")
    st.markdown("[CIDACC · Zenodo DOI 10.5281/zenodo.13219972](https://zenodo.org/records/13219972)")

if data is None:
    st.markdown("### 시작하는 방법")
    st.write("왼쪽에서 **공개 클로렐라 이미지 파일**을 올리거나, 기능 확인용 **합성 데모**를 선택하세요.")
    st.write("실제 검증은 CIDACC `distinct/images`의 파일 10장을 이용합니다. 데이터 원본은 앱에 포함되어 있지 않습니다.")
    st.stop()

try:
    img = read_image(data)
except Exception as exc:
    st.error(f"이미지를 읽을 수 없습니다: {exc}")
    st.stop()

img_hash = image_sha256(data)
if img_hash != st.session_state.image_hash:
    reset_image_state(img_hash)

cfg = Config(mode=mode, sensitivity=sensitivity, min_area=min_area, max_area=max_area)
run_id = analysis_id(img_hash, cfg.__dict__)
current = st.session_state.analysis
valid = bool(current and current.get("run_id") == run_id)

top1, top2, top3, top4 = st.columns([2, 1, 1, 1])
with top1:
    st.markdown(f"**현재 이미지:** `{filename}`")
    st.caption(f"{img.width} × {img.height} px  · SHA-256 {img_hash[:12]}…")
with top2:
    st.metric("독립 수동 계수", len(st.session_state.manual_points) if st.session_state.manual_finished else "미완료")
with top3:
    st.metric("자동 계수", current["data"]["count"] if valid else "미실행")
with top4:
    st.metric("검증 기록", f"{len(st.session_state.verified_records)} / 10")

analyze_tab, manual_tab, results_tab, guide_tab = st.tabs([
    "① 자동 분석·수정", "② 독립 수동 계수", "③ 비교·다운로드", "④ 사용법·포트폴리오"])

with analyze_tab:
    st.subheader("자동 계수 및 클릭 수정")
    if not st.session_state.manual_started:
        st.warning("권장: 먼저 **② 독립 수동 계수**에서 정답을 기록하면 자동 결과를 보고 영향을 받는 문제를 줄일 수 있습니다.")
    if st.button("🔍 이미지 자동 분석 실행", type="primary", use_container_width=True):
        try:
            result = detect(img, cfg)
            st.session_state.analysis = {"run_id": run_id, "data": result}
            st.session_state.edits = new_edits()
            st.session_state.last_edit_event = None
            st.rerun()
        except Exception as exc:
            st.error(f"분석 오류: {exc}")
    if current and not valid:
        st.warning("설정이 변경되었습니다. **이미지 자동 분석 실행**을 눌러 새 결과를 생성하세요. 이전 분석·수정 결과는 적용되지 않습니다.")
    if valid:
        result = current["data"]
        cells, uncertain = result["cells"], result["uncertain"]
        edits = st.session_state.edits
        st.caption(f"적용 방식: **{result['used_mode']}** · 자동 검출 {len(cells)}개 · 불확실한 큰/불규칙 영역 {len(uncertain)}개(계수 제외)")
        left, right = st.columns([1, 1.15], gap="large")
        with left:
            st.markdown("**원본 이미지**")
            st.image(img, use_container_width=True)
            st.markdown("**검출 이진 마스크(참고)**")
            st.image(result["mask"], clamp=True, use_container_width=True)
        with right:
            st.markdown("**클릭으로 자동 결과 수정**")
            action = st.radio("수정 모드", ["누락 세포 추가", "오탐지 세포 삭제"], horizontal=True)
            overlay = draw_overlay(img, cells, uncertain, edits["deleted"], edits["added"])
            disp, disp_size = display_copy(overlay, 730)
            click = streamlit_image_coordinates(disp, key=f"edit_{img_hash[:12]}_{run_id}")
            pos = handle_click(click, "last_edit_event", disp_size, img.size)
            if pos:
                if action == "누락 세포 추가":
                    changed = add_missing_point(edits, cells, *pos)
                else:
                    changed = delete_nearest(edits, cells, *pos)
                if changed:
                    st.rerun()
                else:
                    st.toast("해당 위치를 수정할 수 없습니다. 다른 세포 위치를 클릭해 보세요.")
            a, b, c = st.columns(3)
            a.metric("자동", len(cells))
            b.metric("추가/삭제", f"+{len(edits['added'])} / -{len(edits['deleted'])}")
            c.metric("수정 후", corrected_count(len(cells), edits))
            if st.button("↩ 마지막 수정 취소"):
                if undo(edits):
                    st.rerun()
            st.caption("🟢 자동 탐지 · 🔴 삭제된 탐지 · 🔵 수동 추가 · 🟠 불확실 영역(미계수)")
            if len(uncertain):
                st.warning("주황색 영역은 자동으로 정확하게 계수하지 않은 영역입니다. 후속 학습형 AI 개선 대상으로 기록하세요.")
    else:
        st.info("위 버튼을 눌러 자동 분석을 시작할 수 있습니다.")

with manual_tab:
    st.subheader("독립 수동 계수")
    st.write("자동 검출 위치를 **보지 않고** 세포 중심을 하나씩 클릭하여 수동 계수합니다.")
    if not st.session_state.manual_started:
        st.info("블라인드 검증을 원하면 자동 분석 결과를 보기 전에 이 작업을 시작하세요.")
        if st.button("🖱 수동 계수 시작", type="primary"):
            st.session_state.manual_started = True
            st.session_state.manual_blind = st.session_state.analysis is None
            st.session_state.manual_finished = False
            st.rerun()
    else:
        if st.session_state.manual_blind:
            st.success("자동 분석 실행 전에 수동 계수를 시작한 기록입니다.")
        else:
            st.warning("자동 분석 실행 후 시작한 수동 계수입니다. 검증표에 비블라인드로 표시됩니다.")
        st.metric("수동으로 표시한 세포", len(st.session_state.manual_points))
        # No automatic markers are drawn in this tab.
        manual_view = draw_overlay(img, [], show_auto=False, manual=st.session_state.manual_points)
        disp, disp_size = display_copy(manual_view, 760)
        if not st.session_state.manual_finished:
            manual_action = st.radio("수동 작업", ["세포 표시", "마커 삭제"], horizontal=True)
            click = streamlit_image_coordinates(disp, key=f"manual_{img_hash[:12]}")
            pos = handle_click(click, "last_manual_event", disp_size, img.size)
            if pos:
                st.session_state.manual_history.append(deepcopy(st.session_state.manual_points))
                if manual_action == "세포 표시":
                    from core.editor import add_point
                    changed = add_point({"added": st.session_state.manual_points, "deleted": [], "history": []}, *pos)
                else:
                    changed = remove_nearest_manual(st.session_state.manual_points, *pos)
                if changed:
                    st.rerun()
                else:
                    st.session_state.manual_history.pop()
            u, f = st.columns(2)
            with u:
                if st.button("↩ 수동 작업 취소") and st.session_state.manual_history:
                    st.session_state.manual_points = st.session_state.manual_history.pop()
                    st.rerun()
            with f:
                if st.button("✅ 수동 계수 확정", type="primary"):
                    st.session_state.manual_finished = True
                    st.rerun()
        else:
            st.image(disp, caption="수동 정답 마커 (자동 검출 미표시)")
            st.success(f"수동 계수 확정: {len(st.session_state.manual_points)}개")
            if st.button("수동 계수 다시 시작 (기존 기록 삭제)"):
                st.session_state.manual_points = []
                st.session_state.manual_history = []
                st.session_state.manual_finished = False
                st.session_state.last_manual_event = None
                st.session_state.manual_blind = False  # retaking after observing results is not blind
                st.rerun()

with results_tab:
    st.subheader("검증 결과 및 데이터 내보내기")
    if not valid:
        st.info("자동 분석을 먼저 실행해야 결과를 내보낼 수 있습니다.")
    else:
        result = current["data"]
        edits = st.session_state.edits
        auto = result["count"]
        corrected = corrected_count(auto, edits)
        manual = len(st.session_state.manual_points) if st.session_state.manual_finished else None
        met = error_metrics(auto, manual)
        met_corr = error_metrics(corrected, manual)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("자동 계수", auto)
        c2.metric("수정 후 계수", corrected)
        c3.metric("독립 수동 계수", manual if manual is not None else "미완료")
        c4.metric("자동 절대오차", met["absolute_error"] if met["absolute_error"] is not None else "—")
        if manual is not None:
            st.markdown(f"**자동 계수 백분율오차:** {str(met['percentage_error'])+'%' if met['percentage_error'] is not None else 'N/A (수동 계수 0개)'}")
            st.caption("수정 후 절대오차: " + str(met_corr["absolute_error"]) + "개 · 자동 계수의 성능과 구분해야 합니다.")
        else:
            st.warning("② 독립 수동 계수를 완료해야 오차율이 계산됩니다.")
        note = st.text_area("실패 사례·관찰 기록 (선택)", placeholder="예: 흐릿한 세포 2개를 놓쳤다. 민감도를 조정했다.", key=f"note_{img_hash[:12]}")
        row = analysis_row(filename, img_hash, cfg, result, edits, manual, st.session_state.manual_blind, note)
        csv_data = csv_bytes([row])
        annotated_bytes = make_annotated_png(img, result["cells"], result["uncertain"], edits,
                            f"Chlorella Vision | Auto:{auto} | Corrected:{corrected} | Manual:{manual if manual is not None else 'N/A'} | {cfg.algorithm_version}")
        d1, d2 = st.columns(2)
        with d1:
            st.download_button("📸 분석 마커 PNG 다운로드", data=annotated_bytes,
                               file_name=f"chlorella_{img_hash[:8]}.png", mime="image/png", use_container_width=True)
        with d2:
            st.download_button("📊 현재 이미지 CSV 다운로드", data=csv_data,
                               file_name=f"chlorella_{img_hash[:8]}.csv", mime="text/csv", use_container_width=True)
        st.divider()
        st.markdown("### 10장 검증 기록")
        st.write("이미지 하나당 독립 수동 계수를 확정하고 검증표에 추가하세요. 같은 이미지·분석 설정의 기록은 업데이트됩니다.")
        if st.button("➕ 현재 결과를 검증표에 추가", disabled=manual is None or src == "합성 데모 이미지"):
            st.session_state.verified_records[row["analysis_id"]] = row
            st.success("검증표에 추가했습니다.")
        if src == "합성 데모 이미지":
            st.caption("합성 데모 이미지는 실제 데이터 검증표에 등록할 수 없습니다.")
        records = list(st.session_state.verified_records.values())
        if records:
            st.dataframe(pd.DataFrame(records)[["image_name", "auto_count", "manual_count", "corrected_count", "absolute_error", "percentage_error", "manual_count_before_auto"]],
                         use_container_width=True, hide_index=True)
            pairs = [(int(x["auto_count"]), int(x["manual_count"])) for x in records]
            st.metric("검증 이미지 자동 계수 평균절대오차 (MAE)", mae(pairs))
            st.download_button("📁 누적 검증표 CSV 다운로드", csv_bytes(records),
                               file_name="chlorella_validation_results.csv", mime="text/csv")
            st.caption("브라우저를 새로고침하거나 세션이 종료되면 누적 기록이 사라질 수 있습니다. 반드시 CSV를 저장하세요.")
        else:
            st.caption("아직 저장된 실제 이미지 검증 결과가 없습니다. 처음에는 10장부터 시작합니다.")

with guide_tab:
    st.subheader("기술 설명 및 연구 윤리")
    st.markdown("""
**이 앱은 무엇인가요?**  
이미지 처리(OpenCV)로 세포처럼 보이는 영역을 찾는 교육용 도구입니다. 학습 데이터로 신경망을 훈련한 AI가 아닙니다.

**추천 검증 순서**
1. CIDACC `distinct/images`에서 서로 다른 사진 10장을 선택합니다.
2. 먼저 **② 독립 수동 계수**에서 자동 마커 없이 직접 셉니다.
3. **① 자동 분석**을 실행하고 결과를 비교합니다.
4. 필요하면 잘못된 마커를 삭제하고 누락된 세포를 추가합니다.
5. **③ 검증·다운로드**에서 오차와 실패 사례를 기록하고 CSV를 저장합니다.

**수치 해석 시 주의**
- 이미지 한 장의 검출 개수는 배양액의 세포/mL가 아닙니다. 계수판 부피·희석배수 등의 별도 정보가 필요합니다.
- px² 단위 면적은 보정 없이 µm²로 환산할 수 없습니다.
- 주황색 불확실 후보는 정확한 세포 수에 포함하지 않습니다.
- 수정 후 수치가 정답에 가깝더라도 그것을 자동 분석 정확도라고 주장하면 안 됩니다.
- 직접 촬영한 사진이 아닌 데이터셋 이미지는 출처를 명확히 밝혀야 합니다.

**후속 AI 발전 계획**  
공개 주석 데이터로 객체 검출/분할 모델을 학습하고, 현재 OpenCV 방식과 같은 시험 사진에서 비교합니다. 특히 뭉침·흐림이 있는 이미지에 초점을 맞춥니다.

**공개 출처**  
Pistolas et al. (2024), *CIDACC: Chlorella vulgaris image dataset for automated cell counting*, Zenodo DOI: [10.5281/zenodo.13219972](https://doi.org/10.5281/zenodo.13219972).

**학생 개발 기록 제안**  
사용한 AI 코딩 도구, 입력한 요구사항, 학생이 직접 수행한 테스트, 발견한 오류와 개선 요청을 날짜별로 기록하세요.
""")
