# View-T 확보 상태와 파일 연동

2026-10-11(한국시간) 현재 **사용자가 제공한 서울 2024년 도로망, 마포구 2023년 경계, 마포구 2024년 평일 연평균 일 추정교통량·평균속도 파일을 확보하고 로컬 검증했다**. 인구 CSV는 토큰키 요구로 미다운로드이며 사용자의 요청으로 수집을 중단했다. 확보 파일의 공식 연평균 집계 어댑터·대시보드 연결은 아직 완료하지 않았다. 기존 파일 업로드·모델·가중치·검증·대시보드는 프로젝트 표준 계약으로 구현하고 실행했다. `examples/viewt/`와 `reports/viewt/`는 전부 **synthetic**이며 공식 다운로드 자료가 아니다. 재개 지점과 발표자료 보유 상태는 [수집 상태 기록](VIEWT_COLLECTION_STATUS.md)을 참조한다.

현재 공식 메뉴에 맞춘 확보 방법은 [다운로드·신청 체크리스트](VIEWT_DOWNLOAD_CHECKLIST.md)를 우선 참조한다. 공식 도로 자료의 **연평균 일/시간 집계**, 차량 경로 API의 **이용비율(%)**, 인구 CSV의 **서두 조건문 및 여러 지표 행**은 아래 일별 `period_total` 계약으로 열 이름만 바꾸어 입력할 수 없다. 원본 샘플과 기관 정의를 확인한 별도 변환·집계 어댑터가 필요하다. 평균일을 여러 날짜로 복제하거나 경로 비율을 차량 대수로 바꾸지 않는다.

## 이전 접근 조사 결과와 재조사

아래 표는 2026-10-10 이전 실행 당시의 기록이며 현재 View-T 접속 상태를 뜻하지 않는다. 2026-10-11(한국시간) `viewt.ktdb.go.kr`는 HTTP 200으로 접속했고, 공식 Open API·Expert·차량통행지표·네트워크·월 속도 화면과 공개 공지 875/545를 읽었다. 문서 예시 API 2건도 HTTP 200 JSON으로 응답했으나 `CNT=0`, `RESULT=[]`여서 사용 가능한 마포구 자료 확보로 세지 않았다. Track 상세 페이지는 여전히 프록시 터널 403이었다. 새 근거: [공식 재조사 기록](../reports/runs/viewt_official_reconnaissance.json).

| 접근 URL | 실행환경에서 확인된 결과 | 확인하지 못한 내용 |
|---|---|---|
| https://viewt.ktdb.go.kr | HTTPS 프록시 터널 403, 재시도 동일 | 실제 화면, 세 도구의 현재 메뉴, 다운로드 형식, API 유무 |
| https://www.ktdb.go.kr | HTTPS 프록시 터널 403 | 자료 신청 메뉴/승인 절차 |
| https://www.koti.re.kr | HTTPS 프록시 터널 403 | 담당 문의처/이용 조건 |
| https://www.data.go.kr/tcs/dss/selectDataSetList.do?keyword=View-T | 503, 재시도 동일 | 관련 공개 API와 활용신청 상세 페이지 |

접속 증거: [viewt_access.json](../reports/runs/viewt_access.json). 네트워크 사용 권한을 받은 뒤에도 프록시 차단이 계속됐다. 도메인을 환경 설정 **초안**에 추가했으나 런타임 접근이 열렸다고 확인되지는 않았다. 자동 승인 심사 거절이나 View-T 제공자의 계정 거절로 단정할 수 없다.

**당시에는 확인된 API endpoint와 신청 경로가 없었다.** 재조사에서는 `mainPath_road.do`, `mainPath_emd.do`, `basedPathOD_emd2emd.do` 등의 공식 문서와 게시판 토큰 신청 경로를 확인했다. 인증키를 API 요청의 어느 필드에 넣는지는 해당 상세 문서에 없으므로 추측하지 않는다. 현재 구현은 인증 없이 실행되는 로컬 파일 어댑터이며 공식 API 자동 수집기는 아직 없다. 인증키 자체를 채팅이나 Git에 넣을 필요는 없다.

아래 문구는 이전 일별 자료 요청 초안이다. 공식 평균일 자료 및 현재 토큰 양식에 맞춘 요청문은 새 [체크리스트](VIEWT_DOWNLOAD_CHECKLIST.md)를 사용한다. 일별 원자료 제공 여부는 별도 문의 대상이다.

> 정보통신공학 캡스톤디자인2 및 산업공학회 대학생 경진대회 비상업 연구. 서울 마포구(11440), 동일 조사연도·같은 연속 2주 이상, 시간대별 자료. 인구 O/D·차량 대표 경로·인구 통행구간의 CSV/Excel 및 공간구역 코드 대응표를 요청. 관측/확대추정 구분, 원자료/평균일 집계 여부, 중복 통행 정의, 결측/0 처리, 제공 범위, 재배포·발표 인용 조건, API 또는 파일 제공 방식과 이용승인 절차를 함께 확인.

## 도구별 연결 범위

이 표의 `population_segments`는 프로젝트 자체의 구역별 통행량 계약이다. 공식 **기종점 인구 통행구간 분석**의 CSV는 `Origin ID`, `Destination ID`를 가진 O/D 표이며 보행자가 실제 통과한 도로 링크 궤적이 아니다. 공식 파일은 검토 후 `population_od` 또는 적절한 집계 계약으로 연결해야 한다. 두 인구 도구를 독립 인구량으로 더하지 않는다.

| 요청한 도구/자료 | 입력 계약 | 분석에서 사용하는 의미 | 확보/추가 조건 |
|---|---|---|---|
| 기종점 인구 통행량 분석 | 공식 CSV는 구역별 집계. 프로젝트 `population_segments` 또는 별도 평균일 계약으로 변환 검토 | 유입/유출 조건에 따른 구역별 통행 맥락 | 집계구 ID·경계, 상대 기종점 범위, 총계/평균 정의 필요. 원본 직접 호환 아님 |
| 기종점 차량 경로 분석 | 공식은 링크 순서·이용비율 %. 기존 `vehicle_paths`는 구역 순서·차량 통행량 계약 | 대표/추정 경로와 가상 순회 지원 | 별도 링크 경로·비율 계약 필요. 비율을 대수로 입력 금지. 차량 GPS 아님 |
| 기종점 인구 통행구간 분석 | 공식 CSV는 O/D. 프로젝트 `population_od` 또는 별도 평균일 계약으로 변환 검토 | 구역 사이 인구 O/D. 보행자의 도로별 통과량 아님 | Origin/Destination 코드·경계, 한 지표만 선택, 집계 의미 검토 필요 |
| 도로별 교통량·속도 | 이번 기본 계약에 직접 합산하지 않음 | 도로 링크별 시공간 보조 검증 가능 | 링크 ID·방향·시간 단위·속도 정의·집계기간 확인 및 별도 어댑터 필요 |
| 도로 네트워크·주요 통행경로 | 현재는 구역 순서만 사용 | 가상 순회 연결 관계 | 실제 도로 형상/회전제한/방향성 없는 상태에서 도로 최단경로라고 주장하지 않음 |
| 화물차 통행량 | 차종 미확인 자료를 화물차로 분류하지 않음 | 실제 차종 필드 확보 뒤 별도 분리 | 화물차 기준·차종별 표본/추정 방식 필요 |
| 일반 O/D | 인구 O/D 계약만 구현 | 목적지 유입량 | 차량 O/D·화물 O/D와 단위가 다르므로 별도 구분 필요 |

인구 `segments`와 `od_destination`은 **대안**이다. 둘이 동시에 있어도 메타데이터에서 고른 하나만 산식에 넣는다. 구역 간 경로 통행은 구역별 발생량이지 자치구 전체 고유 통행자 수가 아니므로 구역 합계의 노출 인원 해석을 금지한다.

## 직접 입력하는 형식

**아래는 Transit OOH가 정의한 표준 계약이며, 확인된 View-T 원본 다운로드 형식이 아니다.** 공급자 원본을 보존하고 열 대응·공간 대응 과정을 별도 기록한다. 앱은 공급자 열 이름 → 표준 열 이름 JSON 매핑을 지원한다. 예: `{"population_od":{"출발구역":"origin_id","도착구역":"destination_id"}}`. 날짜/단위 변환과 공간 재집계는 열 이름 변경과 다르며 원본의 정의를 확인해야 한다.

- XLSX 1개: `metadata`, `candidates`, `poi`, `vehicle_paths`, 그리고 `population_segments` 또는 `population_od` 시트.
- CSV 묶음: 같은 표 이름의 CSV와 `metadata.json`. UI에서 함께 선택하거나 CLI에 디렉터리를 전달한다. UTF-8-SIG / CP949를 UI에서 선택 가능. CLI CSV 디렉터리는 UTF-8-SIG 사용.
- metadata 시트는 `json` 열의 첫 셀에 JSON을 넣는다. 전체 예제는 [metadata.json](../examples/viewt/metadata.json). 예제의 synthetic 출처를 실제 데이터처럼 재사용하지 않는다.

| 표 | 필수 열 |
|---|---|
| candidates | zone_id, name, district_code, longitude, latitude |
| population_segments | zone_id, date, hour, population_flow, observation_type |
| population_od | origin_id, destination_id, date, hour, population_flow, observation_type |
| vehicle_paths | route_id, zone_id, sequence, date, hour, vehicle_flow, observation_type |
| poi | zone_id, poi_count, observation_type |

`zone_id`는 분석 공간단위의 코드다. 위경도는 해당 구역의 대표 위치이며 공식 경계나 도로 노드로 자동 인증하지 않는다. UI의 25개 자치구 중심은 지도 초기 위치이며 공식 행정경계 데이터가 아니다. 실제 후보는 검토된 대응표를 사용해야 한다. 자치구 선택 코드와 업로드 코드가 다르면 거부한다.

모든 component 메타데이터에 source/source_url/observation_type/unit/year/timezone/spatial_support_id/spatial_unit/start_date/end_date/coverage가 필요하다. 인구·차량에는 hours와 statistic=`period_total`, 차량에는 path_semantics, POI에는 valid_from/valid_to가 추가된다. View-T 자료가 통신/내비게이션 표본에서 확대 추정한 통행량이면 기관 자료라도 `estimated`로 선언한다. 앱은 선언의 내부 일관성을 검증하며 출처 진위를 인증하지 않는다.

## 정합성 검사와 지원하지 않는 변환

- 자치구, 공간단위, 공간 코드 버전, 동일 조사연도·분석기간, Asia/Seoul 시간대, 선택 시간대, 단위를 검사한다. 불일치는 자동 보간하지 않고 중단한다.
- 인구 통행구간 표는 후보 × 일자 × 시간의 완전한 행을 요구한다. 인구 O/D와 차량 대표경로는 제공 범위가 완전하고 없는 행이 구조적 0인 경우만 허용한다(`complete_with_structural_zeros`). 미집계·비공개·결측을 0으로 바꾸면 안 된다.
- 개인 수가 아니라 `person_trips`, 차량 수 관측 여부를 확인한 `vehicle_trips`, POI 개수 단위를 요구한다. 평균일 값이나 월간 평균을 실제 일별 총계로 복제해서 Bootstrap하면 안 된다. 현재 구현은 `period_total`만 지원하며 평균일 자료는 일별 원자료를 요청하거나 별도 분석이 필요하다.
- 한 route/date/hour에 동일 차량통행량을 요구한다. 같은 구역을 다시 통과해도 route-zone별 한 번만 집계한다. 경로 점 수가 통행량을 늘리지 않는다.
- POI의 누락 구역을 0으로 채우지 않는다. POI 유효기간이 분석기간을 포함해야 하며, 유효기간 선언의 실제 근거는 공급자의 메타데이터로 확인해야 한다.
- 합성·실제 입력의 혼합은 거부한다. 관측·추정 자료의 결합은 각각의 분류를 보존하며 결과는 `assumed_decision_index`다.
- 도로 링크/행정동/집계구 자료를 이름이 비슷하다는 이유로 조인하지 않는다. 행정경계 버전·CRS·공간 중첩 가중을 검토한 대응표가 없는 상태의 자동 공간 조인은 미구현이다.

## 재현 명령

```bash
bash scripts/setup.sh
bash scripts/run.sh transit-ooh viewt --demo --district 마포구 --weight 0.5
bash scripts/run.sh transit-ooh viewt --input examples/viewt/SYNTHETIC_example.xlsx --weight 0.6 --output reports/viewt_60
bash scripts/run.sh transit-ooh viewt --input /path/to/reviewed_csv_directory --hours 8 9 10 --weight 0.7 --output data/processed/viewt
bash scripts/run.sh streamlit run app/streamlit_app.py
```

실제 기관 파일을 연구 결과로 발표할 때는 검증한 입력·변환 스크립트·이용조건·체크섬을 보존한다. 라이선스를 확인하지 못한 원본은 Git에 포함하지 않는다. `examples/viewt/`의 합성 예시만 저장소에 포함했다.
