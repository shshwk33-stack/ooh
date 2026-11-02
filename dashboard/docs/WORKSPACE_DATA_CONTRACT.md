# TRANSIT ATLAS 데이터 연결 계약 v2

동일한 workspace JSON을 파일 가져오기 또는 GET API 응답으로 연결합니다. 화면 상태를 바꾸기 전에 전체 스키마를 검증하며, 실패한 입력으로 현재 자료를 교체하지 않습니다. `workspaceContract.js`가 검증·CSV·API의 단일 진입점입니다.

필수 구조는 `schemaVersion:"2.0"`, `meta`, `geometry`, `candidates`, `gps`, `bootstrap`입니다. 개발 예시는 `workspaceData.js`의 `DEFAULT_WORKSPACE`를 JSON으로 저장해 사용할 수 있습니다.

내장 후보의 지리 좌표는 후보 ID에 명시적으로 매핑한 수기 시나리오 앵커입니다. 공식 역 위치의 측량·지오코딩 결과가 아닙니다. 원문 경계의 `covers`로 행정동 코드만 검증했으며, 실제 관측 후보 좌표를 연결할 때는 제공자의 원천 좌표·출처로 교체합니다.

- `meta`: id/name/version/region, period `{start,end,timezone}`. 시각은 offset 포함 ISO8601, timezone은 IANA 이름. sources는 고유 id·label·kind를 명시합니다.
- source.kind: OBSERVED_GPS / PUBLIC_AGGREGATE / ESTIMATED / SYNTHETIC / DERIVED. 출처 라벨은 진위 인증을 대신하지 않습니다.
- `geometry`: crs `EPSG:4326`, district/units/roads/routes/population/poi 각각 GeoJSON FeatureCollection. 미확보 레이어도 빈 features 배열로 유지합니다. units의 properties.code는 고유 문자열 코드입니다.
- `candidates`: id/name/short/longitude/latitude/unitCode/sourceId/mobility/spatial. 점수는 이미 방향·범위가 맞춰진 0–1 숫자 또는 null입니다. 정규화 방법은 제공자가 meta.scoreMethod에 기록해야 합니다. geometry/coordinates가 점수를 대신 만들지 않습니다. 선택 metrics는 0 이상 숫자 또는 null입니다. 단위는 별도 metricUnits 객체로 기록합니다. 예: `{traffic:"대/일",population:"명/일",poi:"개"}`. 미확인 단위는 빈 문자열 또는 키 생략으로 둡니다.
- `gps`: sourceId, positions 배열. 각 기록 id/vehicleId/timestamp/longitude/latitude/unitCode. 같은 차량·시각의 중복은 거부합니다.
- `bootstrap`: 미계산일 때 반드시 null. 결과가 있으면 DERIVED sourceId, iterations/seed/resampleUnit/weight/topK/period/results가 필요합니다. results는 `{candidateId,meanRank,rankSD,topKProbability}`입니다. 현재 가중치·기간·전체 후보집합과 일치할 때만 결과를 표시합니다.

자료는 최대 10MB, 후보는 1,000개, GPS는 50,000개, 각 레이어는 20,000개 피처·300,000좌표로 제한합니다. 지도 표시 범위는 경도 ±180°, 위도 ±85°입니다. 브라우저 기하 검증은 형식·좌표·ring closure 검사이며, 원천 형상의 위상 검증을 대체하지 않습니다.

## 계산과 필터

V=αM+(1−α)S 하나의 계산으로 KPI·순위·기여도·지도·민감도·CSV를 갱신합니다. 필요한 점수가 없으면 null이며, 0가중치의 미사용 항목은 계산에 요구하지 않습니다. 동점은 후보 ID로 정렬합니다. Spatial Only와 Mobility Only, Integrated는 같은 후보 집합을 사용하며 Spearman은 평균 동점 순위, Kendall은 tau-b, Top-K는 일치 후보 비율입니다.

현재 후보 점수 계약은 정적입니다. 차량·날짜·시간 필터는 GPS 위치기록을 조회하며, 근거 없는 시간 배율로 후보 점수를 바꾸지 않습니다. GPS는 meta.period 안의 기록만 조회합니다. 같은 분석기간에서 API가 재계산한 후보 점수를 제공하려면 새 workspace 응답을 가져옵니다.

## CSV

필수 헤더: `id,name,short,longitude,latitude,mobility,spatial,unit_code,source_id,source_label,source_kind,period_start,period_end,timezone`.

UTF-8/BOM과 RFC4180 인용 문자열을 지원합니다. 점수의 빈 칸은 null이고 수치 오류·중복 헤더·출처 충돌·서로 다른 분석기간은 거부합니다. CSV는 후보와 점수 출처를 교체하고 기존 지리/GPS 원천은 보존합니다. 따라서 새 기간 밖의 보유 GPS는 화면 집계에 포함되지 않습니다. API 비밀정보를 파일에 넣지 않습니다.

## API

GET HTTP(S) 주소에서 `application/json` 또는 JSON suffix MIME으로 위 workspace를 반환합니다. 15초 timeout, 최대 10MB를 적용하며, redirect와 URL 내 인증정보·비밀키 query는 거부합니다. `credentials:omit`으로 호출하므로 인증은 별도 서버 프록시에서 처리합니다. View-T 엔드포인트나 필드를 추측하지 않습니다.

파일로 연 HTML에서 원격 API를 호출하려면 API 서버가 해당 요청의 CORS를 허용해야 합니다. 브라우저 CORS를 끄지 않습니다. 배포형에서는 같은 출처 프록시를 권장합니다. 연결 실패·JSON 검증 오류는 화면에 원인을 표시하고 기존 자료를 보존합니다.
