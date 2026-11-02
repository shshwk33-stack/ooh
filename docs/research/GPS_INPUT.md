# GPS 입력 검증과 합성 검증자료

이 모듈은 Phase 1의 **GPS CSV 입력·품질 검증**입니다. 실제 배송차량 운행기록은 현재 확보되지 않았습니다. 정차·방문 이벤트, Mobility/Spatial 점수, 광고 노출량, Bootstrap을 계산하지 않습니다. 기존 대시보드나 점수식도 변경하지 않습니다.

## 입력 계약

UTF-8 CSV의 필수 컬럼은 `vehicle_id,timestamp,longitude,latitude`입니다. `timestamp`는 UTC offset을 포함한 ISO 8601 값이어야 하며 메타데이터의 `source.timezone` IANA 시간대와 일치해야 합니다. 좌표는 EPSG:4326 `[경도, 위도]`입니다. 선택 컬럼 `speed_kmh`, `link_id`를 보존합니다. 실제 도로 파일이 없으므로 링크 ID의 도로망 일치 여부는 검사하지 않습니다. 빈 GPS 템플릿은 `research_data/templates/gps.csv`입니다.

메타데이터는 `schema_version: "1.0"`, `dataset_kind: "vehicle_positions"`와 다음 항목을 요구합니다.

```json
{
  "source": {
    "kind": "OBSERVED_GPS 또는 SYNTHETIC",
    "name": "자료명",
    "sha256": "CSV 원본 바이트 SHA-256",
    "timezone": "Asia/Seoul",
    "provenance": "원천기관·확보 경로·관측 또는 생성 방법"
  },
  "spatial": {
    "input_crs": "EPSG:4326",
    "coordinate_order": "longitude_latitude"
  }
}
```

메타데이터의 `OBSERVED_GPS` 표기는 제공자의 출처 주장입니다. 스키마 검증 통과가 실측 진위, GPS 정확도 또는 연구 타당성을 인증하지 않습니다. `SYNTHETIC`에는 `generator.seed`, `generator.method`가 추가로 필요하며 CSV 모든 행에 `data_type=SYNTHETIC`이 남아 있어야 합니다. 생성기 메타데이터나 행 내 표기가 남은 파일을 `OBSERVED_GPS`로 바꾸면 거부합니다. 원본과 메타데이터를 모두 악의적으로 수정한 경우까지 진위를 식별하는 보안 인증 체계는 아닙니다.

## 실행

프로젝트 루트에서 실행합니다. GPS 모듈 자체는 Python 표준 라이브러리만 사용합니다.

```sh
python -m pipeline.gps_input \
  --input research_data/synthetic/mapo-gps-seed42/mapo_synthetic_gps.csv \
  --metadata research_data/synthetic/mapo-gps-seed42/mapo_synthetic_gps.metadata.json \
  --output research_data/runs/gps-seed42

python -m unittest pipeline.tests.test_gps_input -v
```

출력 디렉터리는 비어 있어야 합니다. 원본 또는 메타데이터가 있는 상위 디렉터리를 출력으로 지정하거나 기존 결과를 덮어쓰지 않습니다. Git에서 제외된 `research_data/runs/` 아래 새 폴더 사용을 권장합니다. 모든 결과를 출력 폴더의 형제 임시 폴더에 작성한 뒤 원자적으로 게시합니다. 검증이나 내보내기 중 오류가 나면 부분 CSV·manifest를 제거하고 종료 코드 2와 `quality_report.json`, `processing_log.jsonl`만 남깁니다. 출력 위치 자체가 기존 파일이거나 쓰기 불가능하면 해당 위치를 변경하지 않고 명확한 오류를 반환합니다. 메타데이터 JSON의 중복 키와 NaN·Infinity도 허용하지 않습니다. 성공 시 다음 파일이 생성됩니다.

| 출력 | 내용 |
|---|---|
| `validated_positions.csv` | 차량·UTC 시각 순 정렬, 차량 ID 양끝 공백 제거, 시각 UTC 표준화. 좌표 문자열과 선택 컬럼 보존 |
| `quality_report.json` | 원본 행 수, 파싱 관측 수, 차량 수, 필수값 결측률, 기간, 속도 검사, 오류·경고 |
| `run_manifest.json` | 입력·메타데이터 해시, 버전·매개변수 기반 run ID, 출력 해시, DERIVED 계보와 원천 분류 |
| `processing_log.jsonl` | 검증·내보내기 단계 처리 로그 |
| `execution.json` | Python·플랫폼·실행 시각. 재현성 비교 대상에서 제외 |

동일한 원본·메타데이터·매개변수는 동일한 결과와 run ID를 생성합니다. 메타데이터 파일의 서식까지 바꾸면 파일 해시와 run ID가 달라집니다.

검사는 필수값, 유한 숫자, 경·위도 유효범위, offset과 시간대, 중복 관측, 동일 차량·동일 시각의 위치 충돌, 기록 속도, 연속 관측 사이 haversine 추정 속도를 포함합니다. 기본 최대 속도 120 km/h는 **입력 이상치 점검용 탐색 기준**이며 연구에서 검증된 최적 임계값이 아닙니다. `--max-speed-kmh`로 명시적으로 바꾸고 실행 기록에 남깁니다. 결측·이상치를 임의 보간하거나 삭제하지 않습니다.

## 포함된 합성자료

`research_data/synthetic/mapo-gps-seed42/`는 Python `random.Random(42)`로 생성한 **72행, 차량 2대, 임의 지정 3일, 차량·일별 12개 1분 간격 좌표**입니다. 2013년 공개 마포구 Polygon 내부인지 확인하지만 실제 도로를 따라 운행하지 않으며 경로·정차 특성이 관측으로 검증되지 않았습니다. 2024-05-01~03은 생성 편의를 위한 가상 날짜이지 실제 관측기간이나 경계자료의 기준연도가 아닙니다. 작은 좌표 이동·jitter는 입력 검증용 가정이며 실제 배송행태를 추정한 모델이 아닙니다.

재생성은 기존 결과를 덮어쓰지 않고 새 폴더에 수행합니다.

```sh
python -m pipeline.scenario \
  --boundary public/data/seoul-districts-2013.geojson \
  --seed 42 --output /tmp/mapo-gps-seed42
```

합성자료는 기능 검증용으로만 사용합니다. 이를 실제 배송차량 활동, 광고 접촉기회, 실제 M/S/V 연구결과 또는 선정 안정성으로 보고하지 않습니다. 실측과 합성 자료는 자동 병합하지 않습니다.
