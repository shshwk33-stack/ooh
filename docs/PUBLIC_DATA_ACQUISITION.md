# 실제 공개자료 확보와 재현

2026-10-21. 현장관측 없이 수행할 후보지역 선정 연구에 필요한 자료를 확보했다. 연구 단위는 마포구 행정동이다. 다운로드한 파일이라는 의미의 실제 자료이며, 모든 값을 현장 직접 관측한 것은 아니다. View-T 교통과 서울시 거래는 기관 집계·추정 맥락이다.

## 확보한 입력

| 자료 | 공식 출처·조건 | 원본 SHA256 |
|---|---|---|
| 2024 점포 4분기 | [서울시 OA-22172](https://data.seoul.go.kr/dataList/OA-22172/S/1/datasetView.do), 마포구 5,694행·16동 | `8f9074df5ad133bf574f089a7cec646107b89e32cb1703f3199fe6e076d6b01a` |
| 2025 추정매출 4분기 | [서울시 OA-22175](https://data.seoul.go.kr/dataList/OA-22175/S/1/datasetView.do), 마포구 2,762행·16동 | `caf8596c91ea8865bbb1fbcf940997550452e2b4de9cff8649f663972a90b279` |
| 서울 Level 5.5 도로망 | 사용자가 다시 제공한 `seoul_link_lev5.5_2024.zip`, [View-T](https://viewt.ktdb.go.kr/cong/map/page.do) | `713dc621ce98a820d4ae063bbed32197ca2507fe8488fd945152a3d963107c9a` |
| 교통량·속도 Excel | 사용자가 다시 제공한 `TrafficVolume(LINK).xlsx`, `AverageSpeed(LINK).xlsx`, 2024 평일 연평균 일 | 원본별 해시는 로컬 `data/processed/viewt_official_roads/metadata.json`의 sources에 보존 |
| 공식 동 이름표 | 표준 공개 이름표 조회 `MobileGetAllZoneName.do`, year=2024 | 실행 보고서 sources의 provider_names_sha256 |
| 지도 표시 좌표 | 이전에 공개한 2024년 기관 유입 집계표 `deliverables/viewt_actual/dong_inflow_2024_weekdays.csv` | 실행 보고서 sources의 map_display_points_sha256 |

서울시 파일은 공공누리 1유형 출처표시 자료다. API 인증키 없이 공식 파일 다운로드로 받았다. View-T 원본은 이용자가 제공한 파일을 분석했으며, 새 다운로드 권한을 우회하지 않았다. 기관 원본·개별 O/D·링크별 상세표·키는 Git과 새 패키지에서 제외한다. 공개 산출물은 출처가 표시된 동별 파생 집계와 연구 결과다.

서울시 공식 POST 주소는 `https://datafile.seoul.go.kr/bigfile/iot/inf/nio_download.do?&useCache=false`다. 점포 폼은 `infId=OA-22172, seqNo=빈값, seq=6, infSeq=3`; 거래 폼은 `infId=OA-22175, seqNo=빈값, seq=7, infSeq=3`이다. 파일 목록이 개정되면 공식 페이지의 연도를 다시 확인한다.

수집기 `scripts/collect_seoul_commercial.py`는 TLS 검증, 80MB 한도, ZIP CRC, 기존 캐시 SHA256을 검사한다. 주소·폼·시각·크기·해시·이용조건·기존 2025 예비값 인지 사실은 각 `.provenance.json`에 기록한다. 현재 수정된 과거 파일을 과거 당시의 시점 고정 자료로 부르지 않는다. 확인한 공식 파일 목록에는 2026 ZIP이 없어서 추가 2026 확인은 실행하지 않았다. 별도 API의 가용성까지 조사·부정한 것은 아니다.

## 실제 검증한 연결

- 408개 교통·속도·도로망 링크 ID와 속성이 일치한다.
- 기관 부여 읍면동 코드로 408/408개 링크를 연결하고 도로 연장을 대조했다. 웹 지도 경계로 도로를 임의 배분하지 않는다.
- 서울시 코드와 View-T 코드는 서로 다르다. 지역을 마포구로 제한한 뒤 16개 고유 명칭·2024년·4개 분기·중복 여부로 대응한다.
- 염리동은 보유 도로 맥락이 없어 15개 동만 비교한다. 결측을 교통량 0으로 바꾸지 않는다.
- 전체 점포 열은 일반 점포+프랜차이즈와 5,694행 모두 일치한다. 이를 중복 합산하지 않는다.
- 교통의 평일과 인구의 월~금에서 공휴일 정의가 같은지 불명확하므로 새 축소형 모형에는 인구를 합치지 않는다. 기존 인구 화면·연구는 유지한다.

## 원본부터 재실행

```bash
bash scripts/setup.sh
bash scripts/run.sh python scripts/collect_seoul_commercial.py
bash scripts/run.sh transit-ooh viewt-roads \
  --traffic '/실제/경로/TrafficVolume(LINK).xlsx' \
  --speed '/실제/경로/AverageSpeed(LINK).xlsx' \
  --network /실제/경로/seoul_link_lev5.5_2024.zip --network-year 2024 \
  --output data/processed/viewt_official_roads
# 공식 이름표 응답을 data/raw/viewt_population/zone_names_2024.json에 준비한다.
bash scripts/run.sh python scripts/public_decision_research.py \
  --network /실제/경로/seoul_link_lev5.5_2024.zip
```

공개 이름표 요청은 공식 UI와 같은 POST `https://viewt.ktdb.go.kr/cong/mobilemap/MobileGetAllZoneName.do`, 폼 `year=2024`다. 이번 실행은 인증 없이 `shpMap` 응답을 받았다. 미래에 권한 요청이 생기면 중단하고 정식 절차를 따른다.

입력 파일이 없거나 연도·키·연장이 맞지 않으면 분석은 실패하며 합성자료로 대신하지 않는다. 기관 원본이 없는 환경에서는 배포된 `reports/public_decision`을 사용해 조합 계산과 앱을 실행한다. 원본 단계의 재수집과 공개 집계표 단계의 재현을 구분한다.

## 집계표로 재현

`Transit_OOH_Public_Research_Package.zip`에 전체 코드·고정 의존성·테스트·원본 PoC 회귀 입력·새 결과표·PNG/SVG·연구 문서가 있다. 기관 원본은 별도다. 앱 기본 화면은 실제 공개 집계표를 읽고 슬라이더 변경 시 조합을 재계산한다.

```bash
bash scripts/setup.sh
bash scripts/run.sh pytest
bash scripts/run.sh streamlit run app/streamlit_app.py
```

연구 검증 근거: `reports/runs/public_research_validation.json`. 익명 발표자료와 제출 전 확인은 `deliverables/competition2026/`에 있다. 신청서·교수 추천서·윤리서약서의 실제 서명 및 팀 역할 사실은 사용자 확인이 필요하다.
