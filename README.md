# Transit OOH · 배송 이동정보의 위치가치 연구

**전체 코드·결과 다운로드:** [최신 통합 ZIP](deliverables/Transit_OOH_Full_Code_and_Results.zip) · [Windows/macOS 실행 안내](CODE_PACKAGE_GUIDE.md). 분석 엔진·GIS 앱·테스트·고정 의존성·결과표·그래프와 최신 PM 스타일 PPT/PDF를 함께 제공합니다. 기관 원본과 인증키는 별도입니다.

**2026-10-22 발표자료 재구성:** [PM 스타일 15쪽 PPT·PDF·대본](deliverables/competition2026_pmstyle/README.md) · [발표자료 다운로드 ZIP](deliverables/Transit_OOH_PMstyle_Presentation_Package.zip). 이전 1·2·3차 개발 흐름과 최신 실제 공개자료 실험을 연결했습니다. 기존 발표본과 연구 결과는 보존했습니다.

**2026-10-21 최신 — 현장관측 없는 실제 공개자료 연구:** [새 연구보고서](docs/PUBLIC_DATA_RESEARCH_REPORT.md) · [자료 확보·실행](docs/PUBLIC_DATA_ACQUISITION.md) · [익명 경진대회 발표자료](deliverables/competition2026/README.md) · [코드·표·그림 패키지](deliverables/Transit_OOH_Public_Research_Package.zip). 2024년 점포와 기관 부여 도로–동 코드를 연결한 실제 집계 사례를 추가했습니다. 앱 기본 화면은 **공개자료 · 강건한 후보 선정**입니다. 현장관측은 이번 완료 조건이 아니며, 기존 현장 도구는 선택 기능으로 유지합니다. 새 연구는 후보 행정동 K개 선정의 조건부 효용·최악후회를 비교하며 광고효과나 실제 운행 최적화를 입증하지 않습니다. 아래는 이전 개발 이력도 포함합니다.

정보통신공학 캡스톤디자인2 / 산업공학회 대학생 경진대회를 위한 재현 가능한 GPS·GIS 분석 및 **후보 선정 안정성** 연구 시스템입니다. 기존 GPS 연구를 유지하며 자치구별 교통·인구 통행 자료의 의사결정 분석과 가상 밀크런 비교를 지원합니다. 광고 주목도·노출량·매출·정확도 향상을 입증했다고 주장하지 않습니다.

**최신 코드·검수용 다운로드:** [모델 고도화 패키지 ZIP](deliverables/Transit_OOH_Model_Audit_Package.zip) · [고도화·실험 보고서](docs/MODEL_AUDIT_REPORT.md) · [독립 현장 검증 사용법](docs/FIELD_VALIDATION_GUIDE.md). 실행 코드·테스트·고정 의존성·가공 연구 그림·실제/합성 구분 결과표를 포함합니다. 기관 원본은 포함하지 않습니다.

**2026-10-17 고도화:** 연속 가중치 교차점·동점·최대후회값·Pareto 분석, 정규화 3종/Spatial 내부 비중 점검, 주 단위 Bootstrap, 2024년 공식 동 경계 지도, 경로–도로 교통 맥락을 추가했습니다. 전체 자동검사는 136 passed/원본 PoC 1 xfailed입니다. 독립 현장 검증은 점수 고정·관측 기록·평가 도구를 구현했으며 실제 관측 결과는 아직 없습니다. 자세한 근거와 남은 연구 조건은 고도화 보고서를 참조하세요.

**View-T 실제 연동:** [실제 자료 확보·연동 보고](docs/VIEWT_ACQUISITION_REPORT.md) · [공식 도로 입력](docs/VIEWT_ROADS_INTEGRATION.md) · [가중치 합성 실험](reports/viewt/RESULTS.md). 2026-10-16 현재 공식 인증과 세 도구의 실제 자료 확보를 완료했습니다. 마포구 16개 동 인구·240개 동간 O/D·15개 대표 차량경로·408개 도로를 지원합니다. 일별 인구는 계획 20일 중 19일을 확보해 별도 안정성 분석을 수행했습니다. 기관 집계·추정 자료이며 실제 배송 GPS·광고 노출로 해석하지 않습니다. 동기간 공간 대응·POI와 독립적인 통합 모델 검증은 남아 있습니다.

**실행 결과:** [실험보고서](reports/RESEARCH_RESULTS.md) · [인수 보고서](docs/DELIVERY_REPORT.md) · [데이터 출처](docs/DATA_SOURCES.md) · [연구 프로토콜](docs/RESEARCH_PROTOCOL.md) · [원본 감사](docs/SOURCE_AUDIT.md)

## 설치부터 실행까지

Python 3.12와 `uv`가 필요합니다. 정확한 전이 의존성은 `uv.lock`에 고정했습니다. Linux/macOS/Git Bash에서 저장소 루트 기준:

```bash
bash scripts/setup.sh
# 공개 관측자료: HTTPS 검증·크기 제한·체크섬, 실패 시 nonzero exit
bash scripts/run.sh transit-ooh fetch-public
# 합성 GT + 실제 자료 별도 분석 + 전체 강건성 실험 + 표/그림/보고서
bash scripts/run.sh transit-ooh research
# View-T 표준 파일 계약 검증 및 마포구 합성 예제 실험
bash scripts/run.sh transit-ooh viewt --demo --weight 0.5
bash scripts/run.sh transit-ooh validate --gps data/synthetic/gps.parquet
bash scripts/run.sh pytest --junitxml=reports/runs/tests.xml
bash scripts/run.sh streamlit run app/streamlit_app.py --server.headless true --server.port 8501
```

공개 데이터 다운로드 없이도 `research`와 앱의 **합성 GT 연구 데모**가 실행됩니다. 실패한 다운로드를 실측처럼 위장하지 않습니다. `research --quick`은 반복수를 줄인 CI smoke입니다. 별도 실제 자료 분석 명령은 `bash scripts/run.sh transit-ooh public-analysis`입니다.

`research`는 현재 입력으로 최신 결과를 다시 만듭니다. 원본이 없는 자료의 과거 자동 생성 공개 결과표·그림은 최신 폴더에서 제거하며, 실행별 표는 `reports/runs/<run_id>/tables/`에 보존합니다. 전달된 실측 결과를 그대로 열람하려면 실행 전에 해당 보고서를 확인하세요. OSM의 미래 다운로드는 지도 갱신에 따라 이번 스냅샷과 달라질 수 있습니다.

Windows PowerShell에서는 `uv sync --frozen`, `uv run --frozen transit-ooh research`, `uv run --frozen pytest`, `uv run --frozen streamlit run app/streamlit_app.py`를 사용할 수 있습니다. 이번 인수 검증은 Linux/Python 3.12에서 수행했습니다.

## 실험과 데이터 구분

- **A · synthetic:** 6대×6일 정답 스케줄 GPS와 독립 공간필드. Episode F1/시간 MAE, 3개 모델·레거시 비교, 가중치·격자·노이즈·표본주기·규모·누락, ablation·공선성·placebo·cluster bootstrap·holdout.
- **B · public_observed:** LaDe-D Jilin 실제 기사 배송 이벤트 31,415건·57명. 제공 AOI 키에 의한 작업량 선정 안정성·월별 변화·기사 bootstrap. 연속 차량 GPS나 정차 방문횟수가 아닙니다.
- **C · public_observed:** Amazon 평가 파일의 3,052개 경로, 433,231개 방문지 레코드(Station 포함). 방문순서는 있으나 방문지 도착시각·실측 체류시간은 없습니다. 좌표는 제공자가 교란했습니다.
- **D · public_observed:** 현재 서울 일부 영역의 OSM amenity node 601개. 유동인구·전체 POI 목록이 아닙니다. © OpenStreetMap contributors, ODbL-1.0.

미국 2018 경로·중국 2022 이벤트·현재 서울 POI·합성 GPS는 서로 결합하지 않습니다. **실제 연속 배송차량 GPS + 같은 지역·기간 공간정보 + 독립 결과지표의 통합 실증은 미완료**입니다.

새 Mobility는 정규화한 비정차 구간 존재시간·정차시간·방문횟수의 평균입니다. Integrated = α Mobility +(1−α) Static. 기본 α=.5, 기존 α=.6 및 사용자 설정을 비교합니다. 어느 값도 검증된 최적 가중치가 아닙니다. 입력의 가중합으로 가짜 정답을 만들지 않습니다. 반복방문은 중복계상 진단 후 기본식에서 제외하고 레거시/ablation에 보존했습니다.

정차시간은 표본 수가 아닌 **경과 시간**입니다. 기본 연결 한도는 차량별 중앙 표본주기의 3배를 180~900초로 제한합니다. 고정 180초 정책도 선택할 수 있으며, 야간 단절·비정상 속도를 연결하지 않습니다. 이동시간은 유효 GPS 구간의 직선·일정속도 보간 **추정값**이며 도로 맵매칭이 아닙니다. 배송/신호정차 목적 구분은 보장하지 않습니다.

## 본인 GPS 입력

CSV/Excel/Parquet 필수 열: `vehicle_id,timestamp,latitude,longitude`. 선택 열: `accuracy`(m), `speed`(km/h), `heading`, `route_id`. 출처·유형·관측단위를 열 또는 metadata JSON으로 명시합니다.

```json
{
  "source": "consented_fleet_campaign_identifier",
  "observation_type": "real_observed",
  "observation_unit": "vehicle_gps",
  "crs": "EPSG:4326",
  "timezone": "Asia/Seoul"
}
```

```bash
bash scripts/run.sh transit-ooh analyze --gps data/raw/consented.csv \
  --metadata data/raw/consented.metadata.json --output data/processed/consented
```

공간자료가 없으면 Mobility만 계산하고 Static/Integrated는 결측으로 남깁니다. 공간자료는 `--context`, `--context-metadata`로 입력하며 좌표·지원영역·기간·유형 정합성을 검사합니다. [데이터 계약](docs/DATA_CONTRACT.md)을 참조하세요. 연구지역에 맞는 투영 CRS가 필요합니다. LaDe 이벤트·Amazon 방문지는 연속 GPS 입력으로 거부합니다.

## 결과물

| 경로 | 내용 |
|---|---|
| `src/transit_ooh/` | 품질·투영·정차·시간 집계·모델·실험·다운로드·CLI |
| `reports/viewt/` | 별도 합성 예제의 A/B/C·가중치·Bootstrap 표와 PNG/SVG |
| `examples/viewt/` | CSV·Excel·metadata 합성 입력 예제 |
| `app/streamlit_app.py` | 출처 구분, GIS, 모델/설정 변경, 후보 비교, 다운로드 |
| `reports/tables/` | 자료 유형이 명시된 CSV 결과표 |
| `reports/figures/` | PNG와 SVG 연구 그림 |
| `reports/runs/` | 실행별 표·manifest·seed·코드/데이터/lock 해시·테스트 XML |
| `data/` | 로컬 데이터, Git 제외 |
| `reference/` | 수정하지 않은 첨부 원본 |
| `archive/audit/` | 렌더링·깨끗한 커널 재실행 파일, Git 제외 |
| `docs/` | P0~P7 감사·프로토콜·출처·개정·진행·인수 기록 |

원본 PoC의 알려진 오류 1개를 `strict xfail`로 보존하며 일반 실패와 구분합니다. 원본 코드 셀 14개는 깨끗한 커널에서 실행 성공했고, 저장된 `NameError`는 순차 실행에서 재현되지 않았습니다.

`.env`, 키, 대용량 원본, 기사별 원본 위치정보는 Git에서 제외합니다. Amazon은 CC BY-NC 4.0, LaDe는 논문과 데이터카드의 라이선스 표기가 달라 비상업 연구에 한정합니다. [출처와 조건](docs/DATA_SOURCES.md)을 확인하세요. 변경은 검증 후 작업 브랜치에 정리합니다. 학회 제출은 별도입니다.
