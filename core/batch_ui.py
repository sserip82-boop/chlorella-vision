"""Streamlit entry point for V2; V1 remains accessible unchanged."""
import hashlib
import zipfile
from pathlib import Path, PurePosixPath
import pandas as pd
import streamlit as st
from core.batch import analyze_batch, batch_csv, zip_inputs
from core.detector import Config


def render_batch():
    st.subheader("V2 · CIDACC 10장 일괄 검증")
    st.write("동일한 이름의 이미지와 TXT를 자동 연결합니다. 예: 101.png ↔ 101.txt")
    st.info("OpenCV 계수 오차 검증입니다. 학습형 AI 정확도나 개별 위치 검출 정확도가 아닙니다.")
    st.caption("CIDACC 13219972 기준: 클래스 0 = 개별 세포, 1 = 뭉침(정답 개수 제외). 근거: docs/cidacc_class_audit.md")
    source = st.radio("데이터 준비 방법", ["준비된 CIDACC 샘플 10장", "이미지와 TXT 함께 업로드", "CIDACC ZIP 업로드"])
    files = []
    try:
        if source == "준비된 CIDACC 샘플 10장":
            root = Path(__file__).resolve().parents[1] / "data" / "cidacc_sample"
            files = [(f"distinct/{sub}/{p.name}", p.read_bytes())
                     for sub, ext in (("images", "*.png"), ("bbs", "*.txt"))
                     for p in sorted((root / sub).glob(ext))]
            if len(files) != 20:
                raise ValueError("기본 샘플 파일이 누락되었습니다. 이미지와 TXT 업로드를 선택하세요.")
            st.success("CIDACC 사진 10장과 정답 TXT가 준비되어 있습니다. 아래 일괄 분석 실행을 누르세요.")
            st.caption("출처: Pistolas et al. (2024), [CIDACC · Zenodo](https://doi.org/10.5281/zenodo.13219972), "
                       "[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). 원본 중 10장과 대응 주석을 변경 없이 발췌했습니다.")
            with st.expander("준비된 사진 보기"):
                st.image([data for name, data in files if name.endswith(".png")],
                         caption=[PurePosixPath(name).name for name, _ in files if name.endswith(".png")], width=150)
        elif source == "CIDACC ZIP 업로드":
            up = st.file_uploader("원본 CIDACC-dataset.zip 또는 distinct 폴더 ZIP", type=["zip"])
            if up:
                files = zip_inputs(up.getvalue())
                names = [n for n, _ in files if "/images/" in n and n.lower().endswith(".png")]
                selected = st.multiselect("분석할 사진 (최대 10장)", sorted(names), default=sorted(names)[:10], max_selections=10)
                stems = {PurePosixPath(n).stem.casefold() for n in selected}
                files = [(n, b) for n, b in files if n in selected or
                         (n.lower().endswith(".txt") and PurePosixPath(n).stem.casefold() in stems)]
        else:
            st.write("distinct/images의 사진 10장과 distinct/bbs의 같은 이름 TXT 10개를 함께 선택하세요.")
            uploads = st.file_uploader("PNG 사진과 bbs TXT", type=["png", "txt"], accept_multiple_files=True)
            files = [(u.name, u.getvalue()) for u in uploads]
        mode = st.selectbox("검출 방식", ["auto", "gray", "green"])
        sensitivity = st.slider("민감도", 0, 100, 50, key="batch_sensitivity")
        a, b = st.columns(2)
        minimum = a.number_input("최소 면적(px²)", min_value=1, value=18, key="batch_min")
        maximum = b.number_input("최대 면적(px²)", min_value=1, value=2200, key="batch_max")
        cfg = Config(mode=mode, sensitivity=sensitivity, min_area=minimum, max_area=maximum)
        fingerprint = hashlib.sha256(repr(([(n, hashlib.sha256(d).hexdigest()) for n, d in files], cfg)).encode()).hexdigest()
        if st.button("일괄 분석 실행", disabled=not files, type="primary"):
            with st.spinner("사진과 정답 주석을 비교하고 있습니다…"):
                st.session_state["batch_result"] = (fingerprint, analyze_batch(files, cfg))
        saved = st.session_state.get("batch_result")
        if saved and saved[0] == fingerprint:
            rows = saved[1]
            good = [r for r in rows if r["status"] == "ok"]
            st.write(f"정상 {len(good)}장 / 오류 {len(rows)-len(good)}건")
            if len(good) != 10:
                st.warning("정상 처리된 사진이 10장이 아닙니다. 오류를 확인하거나 사진을 추가하세요.")
            if good:
                st.metric("정상 사진의 평균 절대오차(MAE)", round(sum(r["absolute_error"] for r in good)/len(good), 3))
            table = pd.DataFrame(rows)
            st.dataframe(table.reindex(columns=["image_name", "auto_count", "ground_truth_count", "absolute_error", "percentage_error", "cluster_annotations", "status", "message"]).rename(columns={
                "image_name":"사진", "auto_count":"자동 계수", "ground_truth_count":"정답 개수",
                "absolute_error":"절대오차", "percentage_error":"오차율(%)", "cluster_annotations":"뭉침 주석", "status":"상태", "message":"안내"}), hide_index=True)
            st.caption("오차율 = |자동 계수 − 정답 개수| ÷ 정답 개수 × 100. 정답 0개는 비워 둡니다. 오류 행은 평균에서 제외합니다.")
            st.download_button("전체 결과 CSV 다운로드", batch_csv(rows), "cidacc_batch_validation.csv", "text/csv")
        elif saved:
            st.info("입력 또는 설정이 바뀌었습니다. 일괄 분석을 다시 실행하세요.")
    except (ValueError, OSError, zipfile.BadZipFile, RuntimeError) as exc:
        st.error(f"분석할 수 없습니다: {exc}")
