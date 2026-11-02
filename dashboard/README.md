# TRANSIT ATLAS — 연결형 대시보드

기존 녹색·화이트 UI에 Python 파이프라인의 실제 경계·품질·출처·실행 결과를 연결했습니다. 기본 화면은 **공개자료 · 운행 탐색**, 기존 가중치·순위 기능은 **예시 점수 비교**에서 사용할 수 있습니다.

## 설치 없이 열기

[실행용 ZIP](https://github.com/shshwk33-stack/ooh/raw/refs/heads/transit-atlas-download/downloads/TRANSIT_ATLAS_CONNECTED_RUN.zip)을 다운로드하고 압축을 푼 뒤 `TRANSIT_ATLAS_CONNECTED.html`을 Chrome/Edge에서 여세요. React 코드·CSS·폰트·공간 형상·GPS·품질 보고서를 포함하며 서버나 인터넷 연결이 필요하지 않습니다.

## 연결된 기능

- 실제 마포구 및 16개 행정동 선택·형상·면적·둘레: 2013년 공개 경계.
- 실제 EPSG:5179 투영좌표 기반 지도, 미터 축척, 확대·축소·드래그·전체화면.
- 합성 GPS 72개, 차량 2대, 가상 3일의 좌표를 실제 행정동에 공간결합.
- 차량·날짜·시간대에 따른 KPI·지도·집계표·상세의 공통 상태 갱신.
- 실제 값이 없는 조건은 0과 빈 상태로 표시.
- 경계·이름·합성 경로·GPS 레이어 제어, 운행 범위·선택 동 확대.
- 선택 행정동의 공간정보 / 합성 GPS / 자료 출처 탭.
- 실제 원천·메타데이터·파생 결과의 해시, 형상 위상·좌표 품질·처리 run ID.
- 현재 필터와 자료 분류·출처 ID를 보존하는 CSV, 세션 JSON, 실제 GeoJSON 저장.
- 운행일 비교, 모델 연결 상태, 자료 관리, 보고서·인쇄 화면.

## 자료 해석

경계는 KOSTAT 유래 공개 미러의 **2013년 단순화 형상**입니다. 현행 법정 경계나 공식 면적 통계가 아닙니다. GPS는 seed 42로 만든 **SYNTHETIC 입력**이며 실제 배송차량 경로나 도로망이 아닙니다. 공간집계의 기록 수를 방문 횟수·정차·광고 노출량으로 해석하지 않습니다.

실제 M/S/V·Bootstrap은 산출하지 않았습니다. 예시 점수 비교 화면은 기존 `demo.js`·`demoModel.js` 입력을 사용하며 원천 기반 연구결과와 분리했습니다. 기존 DEMO 60:40·30:70 계산, 슬라이더·후보지·민감도·레이어·CSV 기능을 유지합니다.

## 개발·빌드

프로젝트 루트에서 Node.js 24로 검증했습니다.

```sh
npm ci
npm run dev
npm run build
npm run build:standalone
```

개발 서버는 5180 포트이며 빌드는 `dist-dashboard/`, 단일 파일은 `dashboard/docs/TRANSIT_ATLAS_CONNECTED.html`에 생성됩니다.

Python 파이프라인을 다시 실행한 뒤 입력을 새로 묶으려면 [연구 실행 문서](../docs/research/README.md)를 따라 결과를 검증하고 exporter의 검증 대상 경로를 명시적으로 갱신합니다.

```sh
.venv-analysis/bin/python scripts/export_dashboard_data.py
.venv-analysis/bin/python scripts/export_dashboard_data.py --check
```

이 exporter는 원천·메타데이터·결과의 SHA-256과 파이프라인 상태를 확인한 뒤 미터 좌표·공간결합·출처를 내보냅니다. 원본을 덮어쓰지 않고 `dashboard/src/research-data.json`만 생성합니다. 원본이 바뀌면 기존 해시로 통과시키거나 조용히 예시값으로 대체하지 않습니다.

## 검증

```sh
npm test
npm run test:demo
npm run test:connected
npm run test:dashboard
ATLAS_STANDALONE=dashboard/docs/TRANSIT_ATLAS_CONNECTED.html npm run test:connected
```

브라우저 검사는 개발 서버와 Chromium을 사용합니다. 마지막 명령은 서버 대신 완성된 단일 HTML을 렌더링하고 화면 조작과 외부 요청 부재를 검사합니다. 이 환경의 Chromium은 file URL을 정책상 열 수 없으므로 로컬 파일 더블클릭 자체를 검증했다고 보고하지 않습니다. 검사는 파일 내용을 같은 브라우저에 직접 렌더링하는 방식입니다.

실제 캡처·결과는 `dashboard/docs/connected/`, 변경 및 검증 보고는 [DASHBOARD_INTEGRATION.md](../docs/research/DASHBOARD_INTEGRATION.md)에 있습니다. 기존 루트 `src/`, 연구 `pipeline/`, 원천 `public/`는 수정하지 않았습니다.
