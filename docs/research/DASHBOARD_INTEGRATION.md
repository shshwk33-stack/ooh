# 대시보드 연결 및 실행 파일 검증

2026-11-02. Phase 1에서 생성한 경계·GPS 입력 검증 결과를 기존 React 대시보드에 연결했다. 이번 작업은 원천 자료나 Python 점수식을 바꾸지 않고 검증된 결과를 화면에서 탐색하도록 만드는 작업이다.

## 실제로 반영한 내용

| 화면 | 연결 내용 |
|---|---|
| 기본 워크스페이스 | 공개자료·운행 탐색을 초기 화면으로 설정 |
| KPI | 실제 행정동 16개, 필터된 합성 GPS 기록·차량·일자, 3개 자료 품질 상태 |
| GIS | 실제 마포구·16동의 EPSG:5179 형상, 미터 축척, 레이어·줌·팬·전체화면 |
| 운행 지도 | 검증된 합성 GPS 72좌표와 차량·일자별 개념 경로 |
| 분석 조건 | 실제 보유 차량·가상 날짜·오전/오후 필터, 빈 상태도 0으로 갱신 |
| 선택 상세 | 지도·표·선택 메뉴와 연결된 행정코드·면적·둘레·GPS 수·출처 |
| 공간집계 | Shapely covers로 실제 행정동에 연결한 합성 포인트 수 |
| 품질·출처 | 원문·메타데이터·결과 해시, 위상·좌표 검사, 파이프라인 run ID |
| 내보내기 | 현재 필터·분류·출처를 보존하는 CSV·세션 JSON 및 실제 GeoJSON |
| 기존 기능 | 예시 점수 비교 모드에 기존 가중치·후보지·민감도·표·지도 조작 보존 |

원천 기반 M/S/V와 실제 Bootstrap을 수행한 것으로 바꾸지 않았다. 예시 점수 화면과 실제 경계 화면은 상단 전환 버튼으로 명확히 분리했다.

## 데이터 연결 구조

```text
원천 GeoJSON / 출처 metadata / Phase 1 manifest·결과
   → scripts/export_dashboard_data.py (해시·상태 검증)
   → 실제 미터 좌표 변환 + 합성 GPS의 행정동 공간결합
   → dashboard/src/research-data.json
   → researchModel.js 공통 필터·집계
   → 지도 · KPI · 상세 · 집계표 · 내보내기
```

묶음은 실제 경계 2013년과 합성 GPS의 가상 날짜 2024-05-01~03을 구분한다. 폰트·형상·위치·품질보고서를 빌드 파일에 포함하므로 실행 중 API·DB·Python 서버가 필요하지 않다. 새 자료를 반영하려면 파이프라인 검증·exporter·빌드를 다시 수행한다. 실행 HTML이 원천 변경을 실시간으로 수집하는 구조는 아니다.

공간결합 결과는 서교동 36개·아현동 24개·염리동 12개이며, 나머지 13개 동은 0이다. 이는 합성 GPS 좌표 수로 방문 횟수나 광고 노출량이 아니다. 공통 경계에 해당하는 모호한 점은 여러 코드의 일치를 기록하고 임의로 한 동에 배정하거나 중복 집계하지 않는다. 현재 기본 자료에는 모호/미일치 점이 없다.

## 설치 없는 파일

`npm run build:standalone`로 `dashboard/docs/TRANSIT_ATLAS_CONNECTED.html`을 생성한다. HTML 안에 JavaScript·CSS·폰트·연구 결과 JSON이 모두 포함된다. 배포 ZIP의 HTML을 Chrome/Edge에서 열면 된다.

브라우저 테스트는 네트워크를 오프라인으로 설정하고 최종 HTML의 내용을 직접 렌더링해 수행했다. 실행 환경 정책이 file URL 자체의 접근을 금지하므로 파일 더블클릭을 직접 실행했다고 주장하지 않는다. 외부 요청·누락 자산·런타임 오류는 0건이며 별도 설치·서버가 필요한 참조는 남기지 않았다.

## 실행한 검사

- `npm run test:demo`: **17/17 통과**. 기존 예시 계산 6개 + 연결 데이터/변환/공간결합/필터/출처/내보내기 11개. 건너뛴 검사 0개.
- `npm run test:connected`: 개발 서버의 **9개 브라우저 검증 그룹 통과**.
- `ATLAS_STANDALONE=dashboard/docs/TRANSIT_ATLAS_CONNECTED.html npm run test:connected`: **오프라인 단일 HTML 9개 그룹 통과**.
- `npm run test:dashboard`: 보존한 예시 화면의 **12개 브라우저 회귀 그룹 통과**.
- `npm run build:standalone`: 운영 빌드·단일 파일 생성 통과.
- `.venv-analysis/bin/python scripts/export_dashboard_data.py --check`: 검증된 입력에서 UI JSON을 재생성했을 때 바이트 단위 일치.

브라우저 검사는 차량·날짜·시간 필터/빈 상태, 실제 경계 선택·표·상세 동기화, 레이어·줌·범위 확대·전체화면, CSV/JSON/GeoJSON, 자료 관리·운행일 비교·미연계 모델 상태, 기존 30:70 점수 0.906, 1440·1536·모바일, 키보드·모달·외부 요청 부재를 포함한다.

실제 캡처와 실행 기록은 `dashboard/docs/connected/`에 있다. Phase 1 Python 테스트 59개 결과는 이전 [Phase 1 보고서](PHASE1_REPORT.md)에 보존되어 있으며 이번에 연구 모듈을 수정하지 않았다.

## 변경 영향

- 기존 `src/`, `pipeline/`, `public/`, 원천 파일 및 기존 `demo.js`·`demoModel.js` 계산은 유지했다.
- 기존 `App.jsx`에 워크스페이스 전환과 공유 사이드바의 자료별 라벨을 추가했다.
- `ResearchWorkspace`·`ResearchMap`·`ResearchPanels`·`researchModel` 및 검증된 JSON, 스타일·테스트·exporter를 추가했다.
- 기존 예시 브라우저 검사는 초기 화면이 바뀐 것에 맞춰 모드 선택만 추가했다.
- API 토큰·인증정보·DB 변경이나 원본 삭제는 없다.
- 작업 전 화면 소스 백업: `/workspace/backups/transit-atlas-before-dashboard-integration/`.

이번 연결은 실제 공간 형상과 처리 근거를 화면에서 확인하는 단계다. 실제 배송 GPS·도로 링크·인구·POI·원천 기반 점수·Bootstrap은 확보·연구 검증이 필요한 후속 범위다.
