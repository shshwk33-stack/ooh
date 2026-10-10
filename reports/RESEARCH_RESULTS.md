# Transit OOH 연구 실험 결과

실행 ID: `20261010T083355097582Z_seed42`. 결과는 실행된 코드에서 자동 작성했다. 원본 입력·코드·의존성 해시는 해당 실행의 manifest에 기록한다.

## 연구 목적과 자료 구분

기존 배송활동의 위치·시간 정보를 추가했을 때 후보지 선정과 안정성이 어떻게 달라지는지 분석한다. 광고효과·주목도·매출·정확도 향상은 검증하지 않았다.

주 실험: **synthetic** GPS 4,167개, 6대, 6일, 독립 스케줄 GT 정차 248개, 동일 후보군 64개. 실제 서울 배송 실증이 아니다. 좌표는 서울 범위지만 궤적·공간값 모두 합성이다. 모델 점수는 `assumed_decision_index`, 구간별 존재시간은 `estimated` 직선 보간이다.

## RQ1 — 시간·공간 분석의 검증

- 탐지 정차 214개, TP 214, FP 0, FN 34.
- Episode precision 1.0000, recall 0.8629, F1 0.9264. 차량 내 1:1 시간 IoU≥0.5 매칭이다.
- 매칭된 episode 정차시간 MAE 8.6916초. 매칭 실패는 이 MAE에서 제외되므로 F1과 함께 해석한다.
- GT 총 정차시간 1199.00분, 추정 1100.00분, 오차 -99.00분.
- 정차 목적 분류기는 없다. 배송 정차와 긴 신호·주차를 GPS만으로 구분했다고 주장하지 않는다.

근거: [stop_validation.csv](tables/stop_validation.csv), [quality.csv](tables/quality.csv), [정차 실패 그림](figures/stop_detection_failure_cases.png).

## RQ2 — 이동정보 추가의 의사결정 영향

동일 후보군 Static-only와 Integrated 순위 Spearman=0.6294, Kendall=0.4885, Top-5 overlap=0.2000. 가중치 α=0.5은 사전적 초기 설정이다. 순위 변화는 산식에 따른 결과이며 정확도나 우월성의 증거가 아니다.

새 Mobility는 정규화한 비정차 구간 존재시간·정차시간·정차 방문횟수의 평균이다. Static은 합성 인구 .7/POI .3이다. 레거시 .4 방문+.4 체류+.2 반복 및 .6M+.4S는 별도 보존한다. 반복방문은 방문횟수와 중복되므로 새 기본 점수에서 제외하고 상관/VIF와 제거 실험으로 진단했다. 상수·완전공선 특성의 VIF는 NA와 플래그로 표시한다.

이동정보는 정적 맥락이 비슷한 격자들의 실제 차량 접촉 차이를 구분하는 데 쓸 수 있다. 이 자료에서는 **시뮬레이터가 정의한 접촉 차이**만 확인했다. 장소의 실제 광고가치에 유용한지는 독립 관측이 필요하다.

근거: [모델 비교](tables/model_comparison.csv), [특성 제거](tables/ablation.csv), [공선성](tables/feature_correlations.csv), [점수 기여도](figures/model_comparison_contributions.png).

## RQ3 — 선정 안정성과 실패 조건

- 가중치 α∈[0,1] 11개 실험에서 기준 대비 Top-K overlap 범위 0.20–1.00.
- 차량 전체 관측일을 묶은 cluster bootstrap 100회; 선정확률≥0.8인 후보 4개. 점수 분위수는 현재 합성 설계에 조건부인 안정성 범위이며 도시 모집단의 신뢰구간이 아니다. 6개 차량 cluster의 작은 유효 표본수를 유의해야 한다.
- 이동특성 벡터를 통째로 다른 격자에 배치하는 placebo 100회로 특성 간 공분산을 보존했다. 광고 라벨이 없어 유의확률·예측정확도 검증으로 해석하지 않는다.
- 노이즈·표본주기·차량수·관측일수·불규칙/누락 57개 실행. 가장 낮은 F1=0.303 (noise=5m, sampling=300s, seed=42). 연결 간격은 차량별 표본주기의 3배를 180–900초로 제한하는 적응형 정책이다. 300초 표본도 분석하나 짧은 정차는 관측되지 않을 수 있다. 별도 detector_benchmark.csv는 미사용 경로 생성 seed 3개에서 짧은 배송·긴 신호·저속 주행·창고 정차와 정확도 누락/과신, 상관 노이즈를 시험한다.
- 100/200/400m 격자와 50/100m 원점 이동을 비교했다. 크기가 다른 격자 ID를 억지로 비교하지 않고 고정 200m 중심점의 공통 지지영역에서 점수를 비교한다. 경계에서 제외된 후보 수는 표에 드러난다.
- 기간·차량·오전/오후 holdout: 훈련 표본의 차량-일당 활동과 min–max 범위를 고정하고 동일 후보들의 순위 안정성을 비교. 공간 holdout: 서쪽에서 정규화, 동쪽 내부에서 두 모델 비교. 계절 검증은 다계절 실측이 없어 **미실행**.

근거: [robustness.csv](tables/robustness.csv), [holdout.csv](tables/holdout.csv), [선정확률](tables/selection_stability.csv), [격자](tables/grid_sensitivity.csv), [탐지 기준](tables/detector_sensitivity.csv).

## 실제 공개 자료 — 별도 기술통계

```json
{
  "amazon": {
    "status": "analyzed",
    "routes": 3052,
    "stop_records": 433231,
    "dropoff_records": 430179,
    "stations": 18,
    "period": [
      "2018-06-01",
      "2018-10-02"
    ],
    "sequence_coverage": 1.0,
    "source_sha256": "dfd8a198b9df5e3b194d3a268f6f442edcd77f028870d54a8d7397a7bc366466",
    "observation_type": "public_observed",
    "unit": "obfuscated_route_stop",
    "continuous_vehicle_gps": false,
    "stop_arrival_or_dwell_time_available": false,
    "integration_with_seoul": "forbidden_geography_and_period_mismatch"
  },
  "lade": {
    "status": "analyzed",
    "rows": 31415,
    "couriers": 57,
    "cities": [
      "Jilin"
    ],
    "provider_date_key_range": [
      512,
      1028
    ],
    "distinct_recorded_days": 163,
    "sample_scope": "full_jilin_partition",
    "duplicate_event_nearest_gps": 0,
    "invalid_coordinates": 0,
    "missing_delivery_gps_fields": 0,
    "source_sha256": "ed0296b83d84f739bb91ab3d3cf1a430cf71e3793e25ddf50f88aa3ef34b51fc",
    "observation_type": "public_observed",
    "unit": "courier_delivery_event_nearest_gps",
    "continuous_vehicle_gps": false,
    "vehicle_type_known": false,
    "crs_timezone_anonymization": "paper section 3.1 states perturbed coordinates, accuracy limited to 10m; datum/timezone unconfirmed; no metric spatial fusion",
    "duration_rule": "accept_to_delivery_is_not_stationary_dwell",
    "event_selection_study": {
      "eligible_AOIs": 356,
      "eligibility": "at_least_10_tasks_and_2_couriers_in_full_observed_panel",
      "courier_clusters": 57,
      "bootstrap_replicates": 200,
      "stable_AOIs_selection_ge_0_8": 0,
      "task_vs_distinct_event_fix_ranking": {
        "n_candidates": 356,
        "spearman": 1.0,
        "kendall": 1.0,
        "top_k": 10,
        "top_k_overlap": 1.0
      },
      "adjacent_month_comparisons": 5,
      "month_top10_overlap_range": [
        0.2,
        0.9
      ],
      "limitations": "available-panel selection; missing operations unknown; events are not continuous GPS or vehicle visits; no external value labels"
    }
  },
  "osm": {
    "status": "analyzed",
    "amenity_nodes": 601,
    "categories": 29,
    "occupied_200m_cells": 12,
    "bbox": [
      126.975,
      37.563,
      126.982,
      37.568
    ],
    "source_sha256": "2a0bb75291aaf3d657e2652f5060f1a1a12e77cf3e5b2ac5448b0be20377a7c0",
    "observation_type": "public_observed",
    "unit": "mapped_amenity_nodes",
    "source": "© OpenStreetMap contributors",
    "license": "ODbL-1.0",
    "period": "current API snapshot; edit timestamps are not observation validity",
    "integration": "spatial-only; not joined with synthetic GPS or foreign historical events"
  }
}
```

Amazon은 방문지·순서이며 도착시각/실측 체류시간이 없다. LaDe는 기사 이벤트 근처 GPS이며 차량의 연속 이동궤적이 아니다. OSM은 현재 지도 편집 스냅샷의 일부 node amenity이며 유동인구가 아니다. 국내 합성 GPS, 중국 이벤트, 미국 방문지, 서울 POI를 교차 결합하지 않았다. 실제 연속 배송차량 GPS와 동기간 공간 맥락의 통합 실증은 **미완료**다.

## 연구적으로 지지되는 것과 지지되지 않는 것

지지: 재현 가능한 분석 시스템이 작동한다. 명시한 합성 조건에서 정차 탐지 성능을 수치로 평가했다. 입력·가중치·관측밀도에 따른 후보 선정 변화와 실패조건을 확인했다. 공개 배송자료의 관측단위를 열어보고 적용 가능한 기술통계를 분리했다.

미입증: 광고효과, 이동정보의 외부 예측 정확도 개선, 최적 가중치, 국내 배송차량 전체로의 일반화, 실제 계절/지역 외삽, 고정밀 도로상의 노출. 독립 광고/전문가 평가 라벨로 입력 가중합을 재검증하는 순환 실험은 만들지 않았다.

## 재현

```bash
bash scripts/setup.sh
bash scripts/run.sh transit-ooh research
bash scripts/run.sh pytest
bash scripts/run.sh streamlit run app/streamlit_app.py --server.headless true
```

네트워크 없는 새 실행에서도 합성 실험은 가능하다. 실측 기술통계를 재생성하려면 공개 데이터 다운로드 또는 보존된 원본이 필요하다. 데이터·라이선스·현재 다운로드 상태는 `docs/DATA_SOURCES.md`와 `reports/runs/public_acquisition.json`을 참조한다.
