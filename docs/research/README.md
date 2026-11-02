# Phase 1 실행·재현 방법

기존 대시보드 UI를 보존하고 별도 Python CLI를 추가했다. 현재 실제 자료는 **2013 서울 자치구 및 행정동 경계**다. 실제 배송 GPS·View-T·인구·POI는 확보되지 않았으며, 이 단계에서 M/S/V·Bootstrap 연구결과를 생성하지 않는다.

## 설치

Python 3.12 권장. 프로젝트 루트에서 실행한다. Node 의존성과 Python 의존성은 분리한다.

```sh
python -m venv .venv-analysis
.venv-analysis/bin/python -m pip install -r requirements-analysis.txt
.venv-analysis/bin/python scripts/run_phase1.py --output research_data/runs/phase1
.venv-analysis/bin/python -m unittest discover -s pipeline/tests -v
```

Windows에서는 `.venv-analysis/bin/python` 대신 `.venv-analysis\Scripts\python.exe`를 사용한다. 출력 폴더가 이미 있으면 기존 결과를 지우지 않고 `phase1-next` 같은 새 이름을 지정한다. 원천자료는 수정하지 않는다.

## 개별 실행

자치구 25개 검증 → 마포구 1개 추출:

```sh
.venv-analysis/bin/python -m pipeline --input public/data/seoul-districts-2013.geojson --metadata research_data/sources/seoul-districts-2013.metadata.json --output research_data/runs/mapo-district --region-code 11140
```

행정동 423개 검증 → 마포구 16개 추출:

```sh
.venv-analysis/bin/python -m pipeline --input research_data/raw/seoul-submunicipalities-2013.geojson --metadata research_data/sources/seoul-submunicipalities-2013.metadata.json --output research_data/runs/mapo-dongs --region-prefix 11140
```

합성 GPS의 별도 입력 검증은 [GPS_INPUT.md](GPS_INPUT.md)를 따른다. `SYNTHETIC` 행 표기와 생성기 메타데이터를 유지하며 실제 경계 결과와 자동으로 합치지 않는다.

## 결과 읽기

| 파일 | 의미 |
|---|---|
| `mapo.geojson` | 선택된 구 또는 16개 행정동. 지도 표시용 EPSG:4326, DERIVED 출처 계보 |
| `districts.csv` | 전체 입력 피처의 속성·미터 면적·둘레. 행정동 입력일 때 423행 |
| `mapo.projected.csv` | 선택된 피처의 EPSG:5179 WKT, 미터 면적·둘레 |
| `quality_report.json` | 스키마·좌표·결측·중복·위상·왕복 변환 검증과 경고 |
| `run_manifest.json` | 입력/메타데이터 해시·조건·모듈 버전·출력 해시·출처 |
| `processing_log.jsonl` | 결정적인 단계별 처리 기록 |
| `execution.json` | 실제 실행시각·Python·Shapely·pyproj·PROJ·플랫폼 |

GeoJSON에 투영좌표를 넣지 않는다. EPSG:5179는 미터 연산용이고, EPSG:4326은 지도 표시용이다. `always_xy=True`로 경도·위도 순서를 고정하고 EPSG:5179 원점과 모든 입력점의 왕복오차를 검사한다. 원본의 CRS 선언이 없다는 사실과 명시적 입력계약은 품질보고서에 남긴다.

입력 SHA-256 불일치, 필수 속성 누락, 비유한 수, 열린 ring, 자기교차, 중복 코드, 기준연도·CRS 불일치 등은 오류다. 형상을 자동 복구하거나 결측을 임의값으로 채우지 않는다. 실패 시 성공용 GeoJSON/CSV는 공개하지 않으며 품질보고서와 로그로 원인을 확인한다. 기존 결과 폴더는 덮어쓰지 않는다.

## 재현성 범위

같은 원본 바이트·메타데이터 바이트·조건·모듈 버전에서 `run_id`가 같고, 고정된 라이브러리 환경에서 분석 결과·품질보고서·처리로그·manifest가 바이트 단위로 같다. 실행시각과 환경을 담은 `execution.json`은 비교 대상에서 제외한다. 서로 다른 Shapely/PROJ/플랫폼에서 마지막 소수점까지 같다는 보장은 하지 않으며 라이브러리 버전을 기록한다.

메타데이터에는 자료 기준연도·출처·입력 CRS·파생 분류가 있다. 현재 점수/정규화/가중치/Bootstrap은 실행되지 않으므로 그 값을 임의로 기록하지 않는다. 입력 GPS 메타데이터의 OBSERVED_GPS 선언 자체가 실측 진위를 보증하지는 않는다.

## 공간 분석 단위에 관한 현재 판단

실제 확보 해상도는 자치구와 행정동이다. 150m/250m/500m 격자나 도로 링크의 관측값이 없으므로 세밀한 히트맵·도로별 점수를 생성하지 않는다. 시군구(5%)와 행정동(1%)은 간소화 정도가 달라 마포구 외곽 면적과 16동 면적 합이 다를 수 있다. 이 차이를 조용히 보정하지 않는다. 면적은 역사적 일반화 형상의 파생값이며 공식 면적 통계가 아니다. 개별 동의 둘레 합에는 공유 내부 경계가 중복 포함되므로 구 외곽 둘레로 읽지 않는다.

## 기존 화면 실행

```sh
npm ci
npm run dev
```

5180 포트에서 기존 UI를 실행한다. 이번 단계는 UI에 계산 결과를 연결하지 않았다. 기존 화면 수치는 여전히 예시 입력이다. `npm test`, `npm run test:demo`, `npm run test:dashboard`로 회귀 검증한다. 브라우저 검사는 개발 서버와 Chromium이 필요하다.

관련 문서: [Phase 0 진단](PHASE0_DIAGNOSIS.md), [공개자료 조사](PUBLIC_DATA_RESEARCH.md), [Phase 1 결과](PHASE1_REPORT.md), [데이터 인벤토리](DATA_INVENTORY.json).
