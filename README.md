# TRANSIT ATLAS

Transit OOH Analytics — 배송차량 이동특성과 도시 공간정보를 결합한 위치가치 분석 워크스페이스.

기존 후보지 평가 UI와 실제 좌표 GIS·자료 관리 기능을 하나로 통합했습니다. 동일한 데이터 계약과 계산 결과로 가중치·KPI·지도·후보 상세·모델 비교·민감도·내보내기를 갱신합니다.

## 바로 실행

[통합 대시보드 ZIP 다운로드](https://github.com/shshwk33-stack/ooh/raw/refs/heads/transit-atlas-download/downloads/TRANSIT_ATLAS_FINAL.zip)

압축을 풀고 `TRANSIT_ATLAS_FINAL.html`을 Chrome/Edge에서 여세요. 서버·설치 없이 기본 자료로 실행합니다. 데이터 관리에서 JSON·CSV를 가져오거나 분석 API 주소를 연결할 수 있습니다. 원격 API 연결에는 해당 서버의 CORS 허용이 필요하며 비밀 인증정보는 서버에서 관리합니다.

## 소스 실행

```sh
npm ci
npm run dev
npm run build
npm run build:standalone
```

개발 서버는 5180 포트, 운영 빌드는 `dist-dashboard/`, 단일 실행 파일은 `dashboard/docs/TRANSIT_ATLAS_FINAL.html`입니다. Node.js 24에서 검증했습니다.

## 데이터·API 연결

[공통 입력 계약 v2](dashboard/docs/WORKSPACE_DATA_CONTRACT.md)에 맞는 JSON을 파일 또는 HTTP GET 응답으로 연결합니다. 후보지역만 교체할 때는 화면에서 저장한 CSV 입력 양식을 사용합니다. 가져오기 실패·HTTP 오류·시간 초과·스키마 불일치 시 기존 자료를 유지합니다.

내장 입력은 `dashboard/src/workspace-default.json`이며 가져오기/API와 같은 형식입니다. 실제 2013년 경계와 시나리오 후보·GPS의 출처를 분리했습니다. 원천 기반 M/S 정규화와 Bootstrap 계산을 브라우저에서 임의 생성하지 않습니다. Bootstrap은 제공된 결과가 가중치·분석기간·후보집합에 맞을 때만 표시합니다.

## 검증

```sh
npm test
npm run test:models
npm run test:unified
ATLAS_STANDALONE=dashboard/docs/TRANSIT_ATLAS_FINAL.html npm run test:unified
```

모델·입력 계약 검사 30개, 통합 브라우저 검사 12개 그룹과 최종 단일 HTML의 오프라인 검사를 통과했습니다. 브라우저 검사는 Chromium과 실행 서버가 필요하며, 마지막 명령은 서버 대신 HTML 내용을 직접 렌더링합니다. API 검사는 localhost의 명시적인 모의 응답으로 정상·오류·늦은 응답을 확인했습니다.

[통합 및 검증 보고](dashboard/docs/FINAL_INTEGRATION.md) · [실제 화면](dashboard/docs/unified/dashboard-unified-1440.png) · [데이터 계약](dashboard/docs/WORKSPACE_DATA_CONTRACT.md)

## 보존한 연구 처리

기존 `src/`, `pipeline/`, `public/`와 원천자료는 보존했습니다. Phase 1 원천 검증·좌표 변환·품질보고서를 재현하려면 [연구 파이프라인 실행 문서](docs/research/README.md)를 참고하세요. 구형 UI 소스와 배포본도 별도로 보존되어 있습니다. 현재 UI 진입점은 `dashboard/src/UnifiedWorkspace.jsx`입니다.
