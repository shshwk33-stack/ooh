# 공개자료 원천 확인 기록

확인일: 2026-11-02 (Asia/Seoul). 조사 범위는 현재 환경에서 접근 가능한 GitHub 공개 저장소와 원문이다. 검색결과의 제목·저장소 설명만으로 실제 관측자료라고 판정하지 않았다. 외부 자료를 기존 원천파일에 덮어쓰지 않았다.

## 확인 결과

현재 실제로 다운로드하고 내용을 확인한 자료는 **KOSTAT 2013 서울 행정구역 경계**다. 기존 시군구 간소화 파일이 공개 원문과 바이트 단위로 같음을 확인했고, 동일 출처의 비간소화 시군구 경계와 읍면동 경계를 추가로 확보했다. 마포구의 16개 행정동을 실제 경계로 표현할 수 있다.

배송차량 GPS, 정차 기록, View-T 도로 통행량·경로, 인구 활동, 상권·POI의 검증 가능한 원천자료는 이번 조사에서 확보하지 못했다. 경계 외 검색 후보는 좌표·원기관·기준기간·사용조건을 충분히 확인하지 못해 분석 입력으로 채택하지 않았다. 따라서 실제 M/S/V 및 광고성과 분석을 완료했다고 해석할 수 없다.

## 검증한 출처·버전·사용조건

- 미러: [southkorea/seoul-maps](https://github.com/southkorea/seoul-maps), 실제 응답 HTTP 200.
- 확인한 커밋: `dbb1dcde2e3c9937684c5a44ab9301888ad63ee6` — GitHub 저장소·디렉터리 페이지의 `currentOid` 확인.
- [고정 README](https://raw.githubusercontent.com/southkorea/seoul-maps/dbb1dcde2e3c9937684c5a44ab9301888ad63ee6/README.md): HTTP 200, 3,110 bytes.
- README의 Sources는 KOSTAT의 `Administrative division geodata for Census (센서스용 행정구역경계), 2013`을 명시한다. 미러 운영자는 원기관 자체가 아니므로 **원기관 유래를 README에서 확인한 공개 미러**로 기록한다.
- README의 Copyright and License는 `Apache v2.0`을 명시한다. 별도 `/LICENSE` 원문 요청은 HTTP 404였다. 원기관 SGIS 이용약관과 원자료의 재배포조건은 이번 조사에서 직접 재확인하지 못했다. 저장소 README의 선언과 원기관 약관 검증 여부를 구분한다.
- 간소화 방식은 README에 시군구 `Visvalingam/weighted area, 5%`, 읍면동 `Visvalingam/weighted area, 1%`로 기재돼 있다. 간소화된 경계로 계산한 면적·교차는 정밀 측량값이 아니다.
- 기준연도는 자료 속성 `base_year="2013"`에서 확인했다. 2024·2026 현행 경계 또는 해당 연도의 교통관측자료라고 표시하지 않는다.

## 실제 확보 파일

| 자료 | 고정 원문 URL | 응답·크기 | 내용·공간해상도 | SHA-256 |
|---|---|---|---|---|
| 시군구 간소화 경계 | [GeoJSON](https://raw.githubusercontent.com/southkorea/seoul-maps/dbb1dcde2e3c9937684c5a44ab9301888ad63ee6/kostat/2013/json/seoul_municipalities_geo_simple.json) | 200 · 57,732 bytes | 서울 25구 Polygon · 마포구 code `11140` | `2bb208614451c9f2a096cd62204063d6b27e57dcb7650a35ac19c06f1a84eb03` |
| 시군구 비간소화 경계 | [GeoJSON](https://raw.githubusercontent.com/southkorea/seoul-maps/dbb1dcde2e3c9937684c5a44ab9301888ad63ee6/kostat/2013/json/seoul_municipalities_geo.json) | 200 · 1,133,982 bytes | 서울 25구 Polygon | `cfa0c49df02184981d3f214b52729685fd5444ec1e58f04054bdf99ae4b1e836` |
| 읍면동 간소화 경계 | [GeoJSON](https://raw.githubusercontent.com/southkorea/seoul-maps/dbb1dcde2e3c9937684c5a44ab9301888ad63ee6/kostat/2013/json/seoul_submunicipalities_geo_simple.json) | 200 · 213,874 bytes | 서울 423개 Polygon · 마포구 16개 | `432bda8622549a53ea51e4a0638baefee9f5214d21065c20457506c9b559291e` |

검증용 다운로드는 `/tmp/atlas-research/pinned-boundary.txt`, `boundary-full.txt`, `submunicipalities.txt`에 보관했다. 확장자는 조사용 임시파일명이며 내용은 GeoJSON이다. 저장소 입력에 채택할 때는 위 고정 URL·해시·원자료 불변 원칙을 유지한다.

기존 `public/data/seoul-districts-2013.geojson`의 SHA-256은 공개 시군구 간소화 원문의 해시와 정확히 일치한다. 원문과 기존 파일 양쪽에서 서울 25개 구, 기준연도 2013을 확인했다.

## 공간정보·품질 확인 범위

- 세 파일 모두 GeoJSON FeatureCollection이며 Polygon 피처다. `code`, `name`, `name_eng`, `base_year` 속성을 포함한다.
- 세 파일 모두 명시적인 `crs` 필드가 없다. 경위도 순서와 GeoJSON 입력계약을 EPSG:4326으로 명시할 수 있지만, 원기관의 공식 투영원본 CRS를 확인한 것으로 표현하면 안 된다. EPSG:5179 변환은 입력계약·변환방식·왕복오차를 별도로 검증한다.
- 기존 간소화 시군구 파일: 25개 닫힌 ring, 1,374개 좌표, 유한한 숫자·유효 경위도 범위 확인, 필수속성 결측 0, `code` 및 `name` 중복 0.
- 이번 외부조사에서 위상 유효성·자기교차·동간 중첩·행정구 전체와 동들의 합집합 차이는 계산하지 않았다. 파이프라인 검증 대상으로 남긴다.
- 마포구 16개 행정동: 아현동, 공덕동, 서강동, 도화동, 상암동, 성산2동, 성산1동, 연남동, 망원2동, 망원1동, 합정동, 서교동, 신수동, 염리동, 대흥동, 용강동. 코드 접두사 `11140`와 파일 속성을 통해 확인했다.
- 시간해상도·관측기간·측정단위는 경계자료에 적용되지 않는다. 도로 통행량·인구수·방문 횟수는 포함하지 않는다.
- 경계의 공개자료 분류와 그 경계에서 생성하는 면적·격자 등의 `DERIVED` 분류를 구분한다. 경계로부터 합성 차량경로를 만들 경우 해당 경로는 `SYNTHETIC`이다.

## 도로·시설 공개자료 후보 조사와 채택하지 않은 이유

| 방문 URL | 실제 응답 | 확인 내용 | 판정 |
|---|---|---|---|
| [GitHub 서울 지하철 검색](https://github.com/search?q=seoul+subway&type=repositories) | 200 | 저장소 검색 결과 228건. 원문 검토 후보를 선정하는 데만 사용 | 검색 건수를 실제 확보 자료 수로 해석하지 않음 |
| [GitHub 서울 OSM 검색](https://github.com/search?q=seoul+osm&type=repositories) | 200 | 검색 결과 10건. 코드·사례연구와 데이터셋을 구분 | 실제 도로 파일 확보로 간주하지 않음 |
| [GitHub 서울 공공자료 검색](https://github.com/search?q=seoul+public+data&type=repositories) | 200 | 검색 결과 91건. 대부분 앱·개인 분석 프로젝트 | 원기관·기간·라이선스 검증 없이 채택하지 않음 |
| [chanyou/open-seoul-subway](https://github.com/chanyou/open-seoul-subway) · [README](https://raw.githubusercontent.com/chanyou/open-seoul-subway/master/README.md) | 200 · 200 | 커밋 `fb4797f91d8ef6621e531b33a1d9cfab12e3f44e`. README는 현재 역 코드와 역간 소요시간 행렬만 제공한다고 명시. Korail·Seoul Metro·서울 열린데이터광장 OA-15442/OA-118 출처 링크 존재 | 현재 파일은 배송차량 GPS·도로 교통량이 아니며, 확인한 파일 목록에 역 좌표 없음. `/LICENSE` 404. 분석 입력 제외 |
| [vuski/seoulsubway](https://github.com/vuski/seoulsubway) · [README](https://raw.githubusercontent.com/vuski/seoulsubway/master/README.md) | 200 · 200 | 지하철 접근성 시각화 코드, `nodeData.js` 등의 파일 존재. README에서 원자료의 관측기간·스키마·데이터 사용조건을 충분히 확인하지 못함 | `/LICENSE` 404. 이름·좌표파일 존재만으로 검증된 시설 원천자료라고 채택하지 않음 |
| [DanJang/Udacity_Project_OpenStreetMap](https://github.com/DanJang/Udacity_Project_OpenStreetMap) · [README](https://raw.githubusercontent.com/DanJang/Udacity_Project_OpenStreetMap/master/README.md) | 200 · 200 | 서울 OSM 데이터 정제 사례연구. 확인한 루트 파일은 문서 중심 | 실제 서울/마포 도로 원본 파일 확보 아님 |
| [youngkil9999/DA-P3-OSM-SEOUL](https://github.com/youngkil9999/DA-P3-OSM-SEOUL) · [README](https://raw.githubusercontent.com/youngkil9999/DA-P3-OSM-SEOUL/master/README.md) | 200 · 200 | 과거 OSM 서울 추출 사례연구, 오래된 Mapzen S3 원문 링크. 루트 파일은 코드·문서 | 과거 보고서의 수치·일부 예시를 현재 도로망이나 실측 차량 이동으로 사용하지 않음 |

다음 자료도 방문했으나 추가 원천 확보로 이어지지 않았다: [SeoulCity GitHub 프로필](https://github.com/SeoulCity)(200, 이 프로필의 기관 공식성 확인 안 됨), `seoul roads geojson` 검색(200, 검색결과 0), `seoul subway data coordinates` 검색(200, 검색결과 0). GitHub의 검색 결과는 조사 시점·쿼리에 한정되며 전체 인터넷에 자료가 없다는 증거가 아니다.

외부 조회는 상속된 프록시와 TLS 검증을 유지했다. 최초 작업공간 네트워크 샌드박스에서 소켓 접근이 거부되어 지원되는 권한 실행 경로로 공개 URL을 조회했다. HTTP 목적지 정책을 우회하거나 자격증명을 변경하지 않았다. View-T 추측 엔드포인트 호출은 하지 않았다.

## 현재 단계에서 할 수 있는 검증과 남은 자료

1. **즉시 가능:** 고정된 공개 경계의 무결성 확인, 마포구·16개 행정동 추출, 명시된 CRS 계약에 따른 미터 좌표 변환, 면적·격자 생성과 공간결합 테스트, 실제 경계를 지도에 표시.
2. **합성자료로만 가능:** 차량·일자·방문·정차 표본을 명시적으로 생성하고 스키마/GPS/정차/M/S/V 계산의 예상값·재현성을 검증. 합성 결과를 실측 연구 결과로 해석하지 않음.
3. **실제 분석에 필요한 자료:** 배송차량의 차량별 timestamp·lon·lat 기록, 실제 도로 링크와 CRS, 기간·단위가 명시된 교통/인구 자료, 좌표·기준일이 확인되는 POI/상권 자료, 라이선스/이용조건, View-T 명세·허용된 인증정보 또는 사용자가 확보한 원본 CSV.

이 기록에서 배송 GPS는 **미확보**다. 공개 행정경계 확보와 실제 배송 이동자료 확보를 구분해야 한다.
