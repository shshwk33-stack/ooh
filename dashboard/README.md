# TRANSIT ATLAS · Transit OOH Analytics

녹색·화이트 연구 대시보드를 기반으로 정보 가독성과 프런트엔드 시연 동작을 고도화한 React 화면입니다. 기존 연구 코드·실데이터·API와 분리되어 있습니다.

## 실행

프로젝트 루트 `/workspace/ooh`에서 실행합니다. Node.js 24에서 검증했습니다.

```sh
npm ci
npm run dev
```

개발 서버는 **5180 포트**입니다. 운영용 빌드는 다음과 같습니다.

```sh
npm run build
npm run preview
```

결과는 `dist-dashboard/`에 생성되며 확인 서버는 5181 포트입니다. 기존 화면은 `npm run dev:legacy`, 기존 빌드는 `npm run build:legacy`로 실행할 수 있습니다.

## 구현한 기능

- 녹색 사이드바, 헤더 조건 선택, 동일 DEMO 데이터에서 파생되는 KPI 5개
- Mobility·Spatial 합계 100% 유지, 프리셋 30:70 / 50:50 / 60:40 / 80:20, 설정 초기화
- 가중치에 따른 Integrated Score·후보지 순위·KPI·기여도·비교표·지도 마커 동기화
- SVG 개념도와 5개 분석 모드: 위치가치, 차량 경로, 인구 통행, 밀크런, POI·상권
- 7개 지도 레이어의 실제 표시·숨김, 확대·축소·드래그·전체화면
- 후보지 선택 공유: 지도·표·상세 패널·차트 범례
- 상세 탭 4개: 개요 / 이동특성 / 공간특성 / 안정성
- 이동 시간대 미니 차트, M·S 막대와 가중 기여도, 조건별 순위
- Top-5 Static(S)·Mobility(M)·Integrated(V) 비교 및 선택 후보 예외 행
- 기본 30–80% 순위 민감도 차트, 범위 밖 가중치에서 0–100%로 자동 확장
- 그래프 마우스·키보드 툴팁, 현재 가중치 수직 기준선
- 별도 고정 DEMO Bootstrap 표와 선정률 막대
- 시나리오 비교·데이터 관리·보고서 화면, 현재 가중치의 DEMO CSV, 인쇄/PDF
- 키보드 지도·차트·탭 조작, 대화상자 포커스 제어, 모바일 메뉴

## DEMO 데이터와 계산 범위

`src/demo.js`는 후보지 ID, 표시 좌표, M/S, 시연 지표와 별도 Bootstrap 예시를 정의합니다. `src/demoModel.js`는 이 샘플에 한정해 다음을 계산합니다.

```text
V = (Mobility 가중치 / 100) × M + (Spatial 가중치 / 100) × S
```

점수 내림차순으로 순위를 정하며 동점은 후보 ID로 정렬합니다. 최고 점수, 평균 점수, 표와 지도 순위는 같은 결과를 사용합니다. Static은 공간 단독 기준, 즉 **Static = S**입니다. 예를 들어 기본 60:40에서는 홍대입구역 1위, 30:70에서는 공덕역 1위로 바뀝니다.

상위 후보지 안정성 KPI는 현재 Top 5에 포함된 후보들의 **별도 DEMO 선정확률 평균**입니다. Bootstrap 값은 고정된 표시 예시이며 실제 재표본추출이나 통계적 검증을 수행하지 않습니다. 이동량 미니 차트와 인구·시설 지표도 시연용 입력입니다.

지역·연도·기간·시간대·운행 시나리오는 UI 조건으로 선택·초기화할 수 있습니다. 실제 연구 계산에 적용하지 않으며 점수 재계산은 **가중치만** 사용합니다. 전체 화면은 DEMO 표시를 유지합니다.

지도는 자체 SVG 개념도입니다. 실제 서울 도로 좌표나 View-T, GPS, 인구 데이터 API를 연결하지 않았으며 지도에 `DEMO / SCHEMATIC MAP`을 명시했습니다. 축척은 UI 예시로 실제 거리 측정에 사용할 수 없습니다.

## 이번 단계에서 연결하지 않은 기능

- 실측 GIS·View-T API·GPS 궤적 처리
- 기존 Python·OR-Tools 연구 엔진 및 실제 점수 재계산
- 실제 Bootstrap·통계적 유의성·광고 효과 검증
- 데이터베이스·인증·서버 보고서 생성

이 항목들은 프런트엔드 작업 범위 밖이며 연결된 것처럼 표시하지 않습니다.

## 검증

```sh
npm test                # 기존 연구 코드 테스트 6개
npm run test:demo       # 프런트엔드 DEMO 일관성 테스트 6개
npm run test:dashboard  # 개발 서버 실행 중 실제 Chromium UI 검증
```

브라우저 검증은 12개 검증 묶음으로 수치 일관성, 순위 역전, 선택 공유, 지도 모드·레이어, 상세 탭, 차트 툴팁, 설정 초기화, CSV, 메뉴, PDF, 반응형 및 외부 요청 부재를 확인합니다. 기본 Chromium은 `/usr/bin/chromium`이며 `CHROMIUM_PATH`로 변경할 수 있습니다. 검증 주소는 `DASHBOARD_URL`로 설정할 수 있습니다.

## 제출물

- [레퍼런스 기준 1536×1024 캡처](docs/dashboard-1536.png)
- [1440×900 전체 캡처](docs/dashboard-1440.png) / [뷰포트 캡처](docs/dashboard-1440-viewport.png)
- [1920×1080 전체 캡처](docs/dashboard-1920.png)
- [모바일 화면](docs/dashboard-mobile.png)
- [인쇄용 DEMO PDF](docs/dashboard-report-demo.pdf)
- [구현·미연결 범위 및 영향 보고서](docs/IMPACT_REPORT.md)
- [전체 소스코드 ZIP](docs/TRANSIT_ATLAS_SOURCE.zip)

이미지는 실제 Chromium 화면입니다. 목업이나 생성 이미지로 대체하지 않았습니다.

## 구성

React 19 / Vite 6 / Lucide / 로컬 Noto Sans KR·DM Sans를 활용했습니다. 기존 라이브러리를 유지하고 지도·차트는 상호작용 가능한 SVG로 구현했습니다. Tailwind·shadcn·Recharts를 추가하지 않아도 현재 요구사항을 충족하므로 불필요한 의존성을 늘리지 않았습니다.

기존 `src/`, `tests/`, `public/`, 루트 `index.html`, `package-lock.json`은 수정하지 않았습니다. 실행 진입점과 소스 영향은 영향 보고서를 참고하세요.

## 최신 레퍼런스 화면 반영

1536×1024 이미지의 헤더·KPI 높이, 3열 패널 폭, 하단 Top-5 표와 그래프 배치를 맞췄습니다. `src/reference.css`가 레퍼런스용 화면 스킨입니다. 오른쪽 상세 패널은 3개 점수 박스, 실제 기여 비율의 녹색·황색 누적 막대, 활동 지표 4개와 선정 이유로 구성합니다. 지도는 같은 계열의 파랑·보라·노랑·빨강 히트맵, 청록색 경로, 선택 후보의 빨간 마커를 사용합니다.

기능과 수치는 공통 DEMO 상태를 유지합니다. 이미지에 적힌 M/S/V가 가중합과 일치하지 않는 부분은 그대로 복제하지 않았습니다. 예를 들어 현재 기본값은 M0.940, S0.780, 가중치60:40으로 V0.876이며, 안정성 KPI는 별도 DEMO 결과의 동일한 집계 기준을 유지합니다.

## 설치 없는 단일 HTML 실행

[실행용 ZIP](docs/TRANSIT_ATLAS_RUN.zip)을 내려받고 압축을 푼 뒤 `TRANSIT_ATLAS.html`을 Chrome/Edge에서 열면 됩니다. React 코드·CSS·한글/영문 폰트까지 파일 안에 포함합니다. 외부 서버나 설치가 필요하지 않습니다.

재생성: `npm run build:standalone`. 생성 위치는 `dashboard/docs/TRANSIT_ATLAS.html`입니다. 네트워크가 꺼진 브라우저에서 HTML 내용을 직접 렌더링하여 화면·슬라이더·지도 모드·상세 탭을 검증했습니다. 이 클라우드 Chromium의 정책상 file URL 자체는 열 수 없어, 로컬 파일 더블클릭 동작을 직접 검증한 것은 아닙니다.
