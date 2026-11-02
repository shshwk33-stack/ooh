# Transit OOH · Location Value Research System

배송차량 이동 기반 위치가치를 탐색하는 React + Leaflet 연구 대시보드입니다. 지도와 후보지 근거, 모델별 순위 변화, 가중치 민감도를 함께 제공합니다.

## 실행 및 검증

Node.js 22 이상 권장.

```sh
npm ci
npm run dev
npm test
npm run build
```

개발 서버 5173 포트 실행 후 `npm run test:browser`로 Chromium 검증을 실행합니다. 기본 경로는 `/usr/bin/chromium`이며 `CHROMIUM_PATH`로 변경 가능합니다.

## 화면

- 좌표 기반 GIS: 도로 교통활동, 밀크런 경로, 인구 활동, POI, 후보지 독립 전환
- 후보별 M/S 기여도, 시간대 계수, 기초 레코드 및 순위 안정성
- Static / Mobility / Integrated 모델 비교
- 21개 가중치 조건의 TOP 3 진입 횟수 및 조건별 순위표
- 지역·시간대 필터, 시나리오 영구 저장/복원/삭제, CSV 출력
- 검증된 도로 GeoJSON 로컬 업로드 (15MB / 20,000 피처 이하)
- 데스크톱/모바일 반응형 화면, 로컬 번들 폰트

[화면 미리보기](docs/dashboard-preview.png) · [연구 맥락과 사용자 설계 피드백](docs/PROJECT_CONTEXT.md)

## 데이터 및 구현 경계

공개 경계는 KOSTAT 2013 자료(southkorea/seoul-maps), 기본 도로/운행/인구/POI 및 점수는 시연 데이터입니다. 출처·적용 상태와 산출 방법은 화면의 데이터 명세에서 확인할 수 있습니다. 기존 `src/model.js` 계산은 보존했습니다. Python 분석 엔진이나 View-T 원천자료 API는 현재 저장소에 없습니다.

GeoJSON 업로드는 실제 지리 좌표 파일을 지도에 표시하며, 기존 점수를 수정하지 않습니다. 선택 `traffic` 속성의 수집연도·단위는 원본 기준으로 확인해야 합니다.
