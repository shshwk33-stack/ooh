# 데이터 계약과 단위

## GPS

WGS84 입력 `vehicle_id,timestamp,latitude,longitude`. 차량 ID는 연구용 가명이어야 한다. offset 없는 timestamp에는 선언한 timezone을 적용하고 UTC로 저장한다. 원본 행 순서의 음수 시간차와 동일 차량·시각 중복을 보고한 뒤 안정 정렬한다. 중복은 먼저 나온 행을 사용한다. 좌표 이상/필수 결측은 제거, 급격한 점프·accuracy>100m 및 해당 연결은 분석에서 제외한다.

`observation_type`: real_observed / public_observed / synthetic / estimated / assumed. 연속 궤적 분석의 `observation_unit`은 vehicle_gps 또는 synthetic_vehicle_gps이다. 기사 이벤트·방문지를 형식만 GPS로 꾸미지 않는다.

## 공간 맥락

좌표 열 `longitude,latitude`, 출처·유형 및 사용 가능한 `population`, `poi_count`를 제공한다. 인구자료는 관측지점인지 격자 중심인지와 지지영역을 기록한다. 행정구역 인구의 임의 격자 배분은 구현하지 않았다. 그런 입력은 별도 검증된 공간 배분 전처리가 필요하다.

메타데이터: `crs=EPSG:4326`, `projected_crs`, `valid_from`, `valid_to`(timezone 포함), `observation_type`, `bbox_projected=[xmin,ymin,xmax,ymax]`, `complete_coverage`. `complete_coverage=true`는 영역 내 결측이 아니라 **관측된 0**으로 처리할 근거가 있을 때만 사용한다. 기본 합성 시나리오만 완전 coverage를 선언하며 OSM node 추출에는 선언하지 않는다.

실제 투영 좌표로 grid_id를 만들고 키 join한다. 국가·CRS 사용영역·기간·유형이 다르면 오류/결측이다. 공간특성이 1종만 있으면 존재하는 특성만 사용하되 모델 정의가 달라졌음을 보고해야 한다.

## 집계와 점수

- 정차시간: episode 마지막−첫 timestamp. 샘플링 경계 오차가 남는다.
- 이동시간: 탐지 정차 밖의 유효 구간. 미탐 정차가 포함될 수 있어 물리적 운행시간과 동일하지 않다.
- 통과: 비정차 연속 경로의 격자 진입. GPS 점 수가 아니다.
- 방문: 탐지 정차 episode 수. 정차 목적은 알 수 없다.
- 반복방문: 차량×격자별 max(정차방문−1,0)의 합. 방문횟수와 연관된다.
- 노출: 관측하지 않았다. 존재시간/POI를 노출량으로 이름 바꾸지 않는다.

점수는 `assumed_decision_index`이며 입력 관측 유형과 별개다. 형식 적합성이 동의·대표성·라이선스·실증 적합성을 보증하지 않는다.
