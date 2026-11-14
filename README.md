# Chlorella Vision · 클로렐라 이미지 자동 계수 웹앱

**상태:** V1 개발용 프로토타입 / 실사용 검증 전  
**용도:** 카카오 AI 루키캠프 포트폴리오, 중학생 연구자의 이미지 처리 및 오차 검증  
**중요:** 이 V1은 OpenCV 기반 *전통적 이미지 처리*이며 학습형 AI 모델은 아직 없습니다.

## 무엇을 할 수 있나요?

- 현미경 JPG/PNG 업로드 → 세포 후보 위치와 **자동 계수** 표시
- 초록색 사진과 회색조 사진 분석 방식 선택 또는 자동 판정
- 민감도, 최소 면적, 최대 면적 조절
- **수정 모드:** 자동 마커를 클릭하여 삭제 / 빠진 세포를 클릭하여 추가
- **독립 수동 계수:** 자동 마커를 숨기고 사람이 세포 위치를 직접 표시
- 자동/수정 후/독립 수동 계수 결과와 절대오차·백분율오차 비교
- 현재 이미지 **주석 PNG**, 결과 **CSV**, 누적 최대 10장 이상 **검증표 CSV** 다운로드
- 확실히 분리되지 않는 큰 뭉침·불규칙 영역은 주황색으로 표시하고 개별 세포 수로 환산하지 않음

> 탐지 표시의 색: 🟢 자동 계수 / 🔴 삭제한 후보 / 🔵 사람이 추가한 후보 / 🟠 불확실 영역(계수 제외).

## 0. 초보자용: 윈도우에서 가장 쉽게 시작하기

1. 이 프로젝트 ZIP을 다운로드 후 **압축 풀기** 합니다.
2. [Python](https://www.python.org/downloads/) 3.11 또는 3.12를 설치합니다. 설치 시 **Add Python to PATH**를 선택합니다.
3. 폴더의 `run_windows.bat`를 **두 번 클릭**합니다. 첫 실행은 인터넷에 연결된 상태여야 합니다.
4. 명령창에 나타나는 `http://localhost:8501`을 크롬 또는 엣지에서 엽니다.
5. 왼쪽에서 **합성 데모 이미지**를 선택하여 버튼과 클릭 작동을 확인합니다.
6. 실제 연구 검증은 아래 CIDACC 이미지를 따로 준비해서 합니다.

프로그램을 닫으려면 명령창에서 `Ctrl + C`를 누릅니다. 앱은 개인 PC에서만 실행되며 이 주소는 외부 공개 링크가 아닙니다.

## 1. 개발자용 실행

Python 3.11/3.12 권장. 파일이 있는 폴더에서:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m streamlit run app.py
```

macOS/Linux:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run app.py
```

**테스트 실행**(개발 전용):

```bash
python -m pip install pytest
python -m pytest -q tests
```

## 2. CIDACC 공개 데이터로 10장 검증하기

데이터 원문: **Pistolas et al., CIDACC (2024), DOI 10.5281/zenodo.13219972**  
[Zenodo 다운로드 페이지](https://zenodo.org/records/13219972)

1. Zenodo에서 `CIDACC-dataset.zip` 파일을 다운로드합니다(원본 ZIP 약 274MB).
2. `distinct`는 개별 세포가 구분되는 이미지이고, `clusters`는 뭉침 영역입니다. V1은 `distinct`부터 시작합니다.
3. 이 프로젝트 폴더에서 예를 들어 다음 명령을 실행합니다.

```powershell
python scripts/prepare_cidacc.py "C:\Users\USER\Downloads\CIDACC-dataset.zip" --output sample_cidacc --count 10
```

4. 만들어진 `sample_cidacc` 폴더의 이미지 파일 10장을 **한 장씩** 웹앱에 업로드합니다.
5. **권장 순서:** ② 독립 수동 계수 먼저 → ① 자동 계수 → 필요하면 클릭 수정 → ③ 검증 결과를 누적 기록.
6. 10장 작업 뒤 `누적 검증표 CSV`를 다운로드합니다. 세션이 종료되면 메모리에 저장된 기록이 사라질 수 있으므로 중간에도 CSV 저장을 권장합니다.

`manifest.csv`의 클래스별 원본 주석 개수는 자동으로 추출한 **미검증 참고 정보**입니다. 원본 bbox class ID(단독 세포 vs 노이즈)의 실제 의미를 먼저 확인해야 하므로, 이를 독립 수동 계수 정답이라고 간주하지 마세요.

**데이터셋 원본은 이 프로젝트 ZIP에 포함하지 않았습니다.** 라이선스와 재배포 범위를 확인하기 전에 GitHub에 원본 사진을 포함하지 마세요.

## 3. Streamlit Community Cloud 배포

1. GitHub에 새 저장소를 만들고 프로젝트 파일을 업로드합니다. `sample_cidacc/`, `CIDACC-dataset.zip`, `.venv/`는 올리지 않습니다(`.gitignore` 확인).
2. [share.streamlit.io](https://share.streamlit.io/)에 GitHub 계정으로 로그인합니다.
3. `Create app`에서 저장소, 브랜치(`main`), 메인 파일(`app.py`)을 선택합니다.
4. 배포를 클릭합니다. 사이트가 준비되면 `*.streamlit.app` 형태의 링크가 만들어집니다.
5. 배포된 웹주소에서 **합성 데모 두 종류**와 실제 CIDACC 이미지를 하나씩 테스트합니다.
6. 앱 링크를 지원서 포트폴리오에 활용합니다. 제출하기 전에 **시크릿 모드에서 외부 접근이 가능한지** 반드시 확인합니다.

> 주의: 이 ZIP만으로 GitHub 저장소나 인터넷 공개 링크가 생성된 것은 아닙니다. 사용자의 GitHub 계정에 업로드 및 배포가 필요합니다.

[Streamlit 공식 배포 문서](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy)

## 4. 정확도 검증 원칙

- **N_auto**: 프로그램이 자동 검출한 수
- **N_corrected**: N_auto − 삭제 수 + 추가 수
- **N_manual**: 별도 수동 계수 모드에서 사용자가 독립적으로 기록한 수
- **절대오차**: `abs(N_auto - N_manual)`
- **절대백분율오차**: `abs(N_auto - N_manual) / N_manual * 100` (수동 계수 >0일 때만)
- **MAE**: 여러 이미지에서 자동 계수 절대오차의 평균

**자동 검출 결과를 먼저 보았다면** 수동 계수는 블라인드 검증이 아닐 수 있습니다. 앱에서 해당 여부를 기록합니다.
**사용자가 클릭으로 수정한 결과**가 정확해도 그 수치를 자동 알고리즘의 정확도로 보고해서는 안 됩니다.

사진 속 세포 수는 세포/mL가 아닙니다. 세포 농도 계산에는 계수판 부피, 희석배수 등 별도 보정 정보가 필요합니다. px² 또한 μm²가 아닙니다.

## 5. 코드 구성

```text
chlorella_vision_v1/
  app.py                        # 웹 UI 및 상태 관리
  core/
    detector.py                 # 기존 이미지 처리 기반 세포 후보 탐지
    editor.py                   # 클릭 추가·삭제 및 좌표 변환
    metrics.py                  # 오차 계산
    exporter.py                 # PNG/CSV 출력
    annotations.py              # CIDACC YOLO 라벨 읽기 보조
    identity.py                 # 이미지별 실행 ID
  examples/                      # 합성 데이터 (실제 세포 아님)
  scripts/
    prepare_cidacc.py           # 사용자가 받은 CIDACC ZIP에서 10장 추출
    make_demo_images.py         # 합성 데모 생성
  tests/                        # 단위 테스트
  docs/                         # PRD, 포트폴리오·검증 가이드
  requirements.txt
  run_windows.bat
```

## 6. 현재 구현/검증 상태

- 완료: 이미지 분석 엔진, RGB/회색조 처리, 수동·자동 결과 분리 구조, 클릭 편집, 계산, CSV/PNG 출력 코드
- 자동 테스트: **11개 통과** (개발 환경, 2026-11-14)
- 합성 데모: 녹색/회색 각각 18개 구분 세포 후보 검출, 큰 영역 1개 불확실 분류. **합성 데이터이므로 연구 정확도 성과가 아닙니다.**
- **미완료:** 실제 CIDACC 10장 독립 수동 계수, 검증표, 외부 PC 브라우저에서 클릭 동작 확인, Streamlit 환경 설치 및 웹 실행, GitHub 업로드, 인터넷 배포, 시연 영상

이번 코드 작성에는 AI 도구를 사용했습니다. 학생이 직접 테스트한 내용은 이후 `docs/development_log.md`에 실제 수행 기록으로 추가해야 합니다.

## 7. 알려진 한계

- 겹친 세포·흐린 세포의 정확한 개별 계수 불가
- 사진 조명과 배경에 따라 민감도 조절 필요
- 대조군에 따라 색상 분할 또는 회색조 임계값 기법이 실패할 수 있음
- 수동 마커와 수정 내역은 서버 세션 메모리에 저장됨(다운로드 권장)
- 큰 사진은 처리 속도 및 클릭 좌표 정확도 별도 확인 필요
- 현재 V1은 딥러닝 학습형 AI 모델이 아님

## 8. 데이터 출처

Pistolas, E. et al. (2024). *CIDACC: Chlorella vulgaris Image Dataset for Automated Cell Counting*. Zenodo. https://doi.org/10.5281/zenodo.13219972

논문: https://pmc.ncbi.nlm.nih.gov/articles/PMC11440301/

데이터셋 라이선스가 명시적으로 확인되지 않은 상태로 판단하여, 원본 데이터를 본 프로젝트의 공개 배포물에 포함하지 않았습니다.
