# TRANSIT ATLAS — 통합 워크스페이스

기존 화면의 가중치·후보지·비교 그래프와 실제 좌표 GIS·품질·데이터 연결을 단일 제품으로 통합했습니다. 별도 예시 화면으로 전환할 필요 없이 같은 후보 선택·가중치·입력 데이터를 공유합니다.

## 기능

- 통합 위치가치 / 이동특성 / 공간특성 / 차량 경로 / 행정경계 지도
- 실제 좌표의 후보 마커·행정동별 후보 점수 평균, 가중치에 따른 동시 갱신
- Mobility/Spatial 합계 100%, 프리셋, 시나리오 저장·복원·삭제
- 후보 상세 4개 탭, 기여도·입력 지표·단위·출처
- Spatial/Mobility/Integrated 비교·가중치 순위·검증 결과 연결
- 실제 도로·POI·인구 레이어 입력 시 활성화, 미확보 레이어는 비활성
- GPS 차량·운행일·시간대 조회, 기간 밖 자료와 빈 결과 처리
- JSON 전체 입력 / CSV 후보지 입력 / HTTP GET API 연결
- 오류·취소·시간 초과·늦은 응답에서 기존 자료 유지
- CSV·전체 JSON·세션 JSON·인쇄 저장
- 키보드·데스크톱·모바일·오프라인 단일 HTML 실행

## 실행

루트에서 `npm ci`, `npm run dev`를 실행합니다. `npm run build:standalone`은 `docs/TRANSIT_ATLAS_FINAL.html`을 만듭니다. 배포 ZIP의 HTML은 Chrome/Edge에서 열면 됩니다.

## 연결 구조

`workspace-default.json` → `workspaceData.js` → `workspaceContract.js` 검증 → `workspaceModel.js` 공통 계산 → `UnifiedWorkspace` / `UnifiedMap` / `UnifiedPanels`.

JSON과 API는 같은 schemaVersion 2.0을 사용합니다. CSV 양식은 데이터 관리에서 저장할 수 있습니다. API 비밀키는 HTML에 저장하지 않으며 서버 프록시에서 관리합니다. [연결 계약](docs/WORKSPACE_DATA_CONTRACT.md)을 참고하세요.

## 자료와 해석

기본 입력은 실제 2013년 행정경계, 수기 시나리오 후보 앵커·M/S, 합성 GPS로 구성되며 분류는 데이터 관리에 명시됩니다. 현재 M/S는 제공된 정규화 입력이며 동반 GPS로 계산한 값이 아닙니다. 차량·날짜·시간 조건은 GPS에 적용하고 정적인 M/S를 임의 배율로 바꾸지 않습니다.

지도 색상은 해당 행정동에 속한 후보 점수의 산술평균입니다. 임의 원형 효과를 밀도나 광고 노출량으로 표시하지 않습니다. 미확보 도로 수·지표·Bootstrap은 값이 연결되기 전까지 비워 둡니다. 실측·집계·추정·합성·파생 출처를 혼용하지 않습니다.

브라우저에서는 EPSG:4326 입력을 EPSG:3857로 표시하고 위도를 보정한 축척을 제공합니다. 과학적 미터 공간 연산·위상 검증은 별도 Python 파이프라인이 담당합니다. 프런트엔드 입력 검증은 형식·좌표·출처·참조·기간을 검사하며 원천 진위를 인증하지 않습니다.

## 검사·제출물

`npm run test:models`: 30개 검사 통과. `npm run test:unified`: 12개 통합 브라우저 그룹 통과. 최종 HTML의 오프라인 검사도 같은 12개 그룹을 통과했습니다. 브라우저 정책상 file URL을 직접 실행한 것이 아니라 HTML 내용을 브라우저에 렌더링해 확인했습니다.

[최종 통합 보고](docs/FINAL_INTEGRATION.md), [1440px 캡처](docs/unified/dashboard-unified-1440.png), [검증 기록](docs/unified/standalone-verification.json).

기존 연구 코드·API 인증정보·DB는 변경하지 않았습니다. 작업 전 백업은 `/workspace/backups/transit-atlas-before-unified/`에 있습니다.
