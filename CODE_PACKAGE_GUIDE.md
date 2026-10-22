# Transit OOH · 전체 코드와 결과 ZIP 실행 안내

이 패키지는 현재 개발한 분석 코드·Streamlit 앱·테스트·실행 설정·결과표·그림·보고서와 최신 PM 스타일 발표자료를 함께 제공합니다. `PACKAGE_MANIFEST.json`은 포함 파일별 SHA-256과 기준 Git 커밋을 기록합니다. 하위 ZIP을 다시 넣지 않아 중복 다운로드를 줄였습니다.

## 먼저 볼 파일

| 목적 | 경로 |
|---|---|
| 실행할 대시보드 | `app/streamlit_app.py` |
| 현재 실제 공개자료 연구 | `docs/PUBLIC_DATA_RESEARCH_REPORT.md` |
| 실제 자료 후보 선정 모델 | `src/transit_ooh/public_decision.py` |
| 기존 GPS·이동·공간 점수 | `src/transit_ooh/` 및 `docs/MODEL_AUDIT_REPORT.md` |
| 독립 수치 검수 코드 | `scripts/check_public_portfolios.py` |
| 실제 연구 결과표·그림 | `reports/public_decision/tables/`, `reports/public_decision/figures/` |
| 최신 PPT·PDF·발표 대본 | `deliverables/competition2026_pmstyle/` |
| 과거 합성 PoC 회귀 입력 | `reference/`의 노트북 1개 |

## Windows에서 실행

Python 3.12와 [uv](https://docs.astral.sh/uv/getting-started/installation/)를 설치하고 ZIP을 완전히 압축 해제합니다. 압축을 푼 폴더에서 PowerShell을 열고 실행합니다.

```powershell
uv sync --frozen
uv run --frozen streamlit run app/streamlit_app.py
```

브라우저에서 `http://localhost:8501`을 엽니다. 기본 화면인 **공개자료 · 강건한 후보 선정**은 함께 제공한 실제 집계표를 사용합니다. 가중치·후보 수·가중치 범위를 바꾸고 점수·순위·강건 후보를 다시 계산할 수 있습니다. 이 기본 화면의 계산에는 API 키가 필요하지 않습니다. 최초 의존성 설치와 외부 배경지도에는 인터넷이 필요합니다.

## Linux·macOS·Git Bash에서 실행

```bash
bash scripts/setup.sh
bash scripts/run.sh streamlit run app/streamlit_app.py
```

## 검수와 실험

```powershell
# Python 표준 라이브러리만으로 실제 주 실험 3,003개 조합 대조
python scripts/check_public_portfolios.py

# 전체 프로그램 검사: 고정 의존성 사용
uv run --frozen pytest

# 합성 GPS 연구 smoke. 합성 자료임을 결과에 표시
uv run --frozen transit-ooh research --quick

# 합성 View-T 표준 입력 예제
uv run --frozen transit-ooh viewt --demo --weight 0.5
```

`research --quick`은 합성 연구 결과를 생성하므로 기존 보고서를 먼저 보존한 뒤 실행합니다. 실제 공개 집계 연구는 `reports/public_decision/`에 별도로 있습니다. 합성 GPS 결과를 실제 마포구 배송 GPS 결과로 해석하지 않습니다.

## 실제 기관 원자료부터 재처리하려면

기관 원본 파일·개별 위치 기록·인증키·가상환경은 포함하지 않았습니다. 기본 공개자료 화면과 독립 수치 검수에는 제공한 집계 결과만으로 충분합니다. 실제 기관 원본부터 다시 집계하려면 `docs/PUBLIC_DATA_ACQUISITION.md`, `docs/VIEWT_ROADS_INTEGRATION.md`, `docs/VIEWT_ACQUISITION_REPORT.md`에 있는 파일·출처·입력 방법을 따릅니다. 기존 공식 도로·인구·경로 화면에서도 해당 원본을 별도로 입력해야 합니다.

## 최신 발표자료를 다시 만들려면

메인 앱 의존성과 발표 제작 의존성은 별도입니다. 발표 재생성은 **Linux에서 검증했으며 Windows에서는 WSL 사용을 권장**합니다. 발표 제작에는 LibreOffice의 `soffice`, Noto Sans CJK KR 글꼴도 설치해야 합니다. 그래프 생성기는 현재 Linux의 `/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc` 경로를 사용합니다.

```bash
python3 -m venv .presentation-venv
.presentation-venv/bin/python -m pip install -r deliverables/competition2026_pmstyle/requirements-presentation.txt
.presentation-venv/bin/python scripts/pmstyle_figures.py
.presentation-venv/bin/python scripts/build_pmstyle_slides.py
```

Windows 네이티브나 macOS에서 발표를 재생성하려면 그래프 생성기의 글꼴 경로를 해당 시스템에 맞게 지정해야 합니다. 제공한 PPT/PDF를 열거나 편집하는 데에는 이 생성 환경이 필요하지 않습니다. 연구 결과표의 해시가 변경되면 발표 생성기가 중단되도록 되어 있습니다. 새로 생성한 PPT/PDF는 다시 시각 검토해야 합니다.

## 자료 해석과 제출

현재 실제 연구는 마포구 15개 후보 행정동의 조건부 선택 비교입니다. View-T는 기관 집계·추정 자료이며 실제 배송차량 GPS, 정차시간, 광고 노출·전환·매출 효과의 관측 정답이 아닙니다. 2025년 거래 관련 검사는 회고적·탐색적 비교입니다.

이 전체 코드 ZIP에는 개발 이력·기존 문서도 들어 있어 익명 심사 제출 파일과 구분합니다. 현재 익명 발표 제출본은 `deliverables/competition2026_pmstyle/Transit_OOH_PMstyle_Anonymous.pdf`입니다. 팀 역할과 공식 별첨은 사용자가 처리합니다.
