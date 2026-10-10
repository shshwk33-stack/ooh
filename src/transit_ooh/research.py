"""Run, export and document measured results from executed experiments."""

from __future__ import annotations
from datetime import datetime, timezone
import importlib.metadata
import json
from pathlib import Path
import subprocess
import shutil
import numpy as np
import pandas as pd
from .io import load_config, save_table, write_json, sha256
from .synthetic import generate
from .pipeline import analyze
from .stops import evaluate_stops
from .experiments import (
    compare_models,
    weight_sensitivity,
    ablation,
    collinearity,
    permutation_placebo,
    cluster_bootstrap,
    holdout,
    robustness,
    grid_sensitivity,
)
from .figures import research_figures, public_figures
from .public_analysis import analyze_public


def code_snapshot():
    paths = [
        Path("pyproject.toml"),
        Path("uv.lock"),
        *Path("src").rglob("*.py"),
        *Path("configs").glob("*.yaml"),
        *Path("app").glob("*.py"),
    ]
    return {str(p): sha256(p) for p in paths if p.exists()}


def git_state():
    head = subprocess.run(["git", "rev-parse", "HEAD"], text=True, capture_output=True)
    if head.returncode:
        return None, None
    status = subprocess.run(
        ["git", "status", "--porcelain"], text=True, capture_output=True
    )
    return head.stdout.strip(), bool(status.stdout.strip())


def run_research(config_path="configs/default.yaml", output="reports", quick=False):
    config = load_config(config_path)
    out = Path(output)
    (out / "tables").mkdir(parents=True, exist_ok=True)
    (out / "runs").mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc)
    run_id = stamp.strftime("%Y%m%dT%H%M%S%fZ") + f"_seed{config['seed']}"
    run = out / "runs" / run_id
    run.mkdir()
    print("Generating labelled synthetic scenario...", flush=True)
    gps, truth, context, meta, schedule = generate(
        seed=config["seed"], **config["synthetic"]
    )
    data = Path("data/synthetic")
    data.mkdir(parents=True, exist_ok=True)
    gps.to_parquet(data / "gps.parquet", index=False)
    truth.to_parquet(data / "truth_stops.parquet", index=False)
    context.to_parquet(data / "context.parquet", index=False)
    write_json(data / "context_metadata.json", meta)
    a = analyze(gps, config, context, meta)
    metrics, matches = evaluate_stops(a.stops, truth)
    print(
        f"Analyzed {len(gps)} GPS fixes, {len(a.stops)} detected episodes; F1={metrics['f1']:.3f}",
        flush=True,
    )
    tables = {
        "quality": a.quality,
        "scores": a.scores.drop(columns="polygon"),
        "stops": a.stops,
        "stop_validation": pd.DataFrame([metrics]),
        "stop_matches": matches,
        "model_comparison": compare_models(a, config["top_k"]),
    }
    tables["weight_sensitivity"], tables["weight_ranks"] = weight_sensitivity(
        a, config["top_k"]
    )
    tables["ablation"] = ablation(a, config["top_k"])
    tables["feature_correlations"], tables["vif"] = collinearity(a)
    n = 10 if quick else config["experiments"]["bootstrap_replicates"]
    tables["bootstrap_replicates"], tables["selection_stability"] = cluster_bootstrap(
        a, n, config["seed"], config["top_k"]
    )
    tables["placebo"] = permutation_placebo(
        a,
        10 if quick else config["experiments"]["placebo_replicates"],
        config["seed"],
        config["top_k"],
    )
    tables["holdout"] = holdout(a, config["top_k"])
    tables["hourly_activity"] = a.detail.groupby("hour", as_index=False)[
        ["moving_seconds", "stop_seconds", "visit_frequency"]
    ].sum()
    print("Running sampling, noise, fleet, period and grid robustness...", flush=True)
    tables["robustness"] = robustness(config, quick)
    tables["grid_sensitivity"] = grid_sensitivity(gps, context, meta, config, a)
    detector = []
    for radius in [15, 30, 60]:
        for minimum in [60, 120, 300]:
            cfg = {**config, "stop_radius_m": radius, "min_stop_seconds": minimum}
            other = analyze(gps, cfg, context, meta)
            m, _ = evaluate_stops(other.stops, truth)
            detector.append({"radius_m": radius, "minimum_seconds": minimum, **m})
    tables["detector_sensitivity"] = pd.DataFrame(detector)
    for name, frame in tables.items():
        save_table(
            frame.assign(run_id=run_id), out / "tables" / f"{name}.csv", "synthetic"
        )
    write_json(
        run / "grid_scores.geojson",
        {
            "type": "FeatureCollection",
            "observation_type": "synthetic",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Polygon", "coordinates": [r.polygon]},
                    "properties": {
                        "grid_id": r.grid_id,
                        "integrated_score": r.integrated_score,
                        "observation_type": "synthetic",
                        "score_type": "assumed_decision_index",
                    },
                }
                for r in a.scores.itertuples()
            ],
        },
    )
    print(
        "Rendering research figures and separate public-data summaries...", flush=True
    )
    figures = research_figures(a, truth, tables, out / "figures")
    public = analyze_public(output=out)
    figures += public_figures(out / "tables", out / "figures")
    head, dirty = git_state()
    manifest = {
        "run_id": run_id,
        "generated_at_utc": stamp.isoformat(),
        "command": f"bash scripts/run.sh transit-ooh research --config {config_path} --output {output}"
        + (" --quick" if quick else ""),
        "seed": config["seed"],
        "quick": quick,
        "config": config,
        "git_head": head,
        "git_dirty": dirty,
        "source_hashes": code_snapshot(),
        "lock_sha256": sha256("uv.lock"),
        "data_hashes": {str(p): sha256(p) for p in data.iterdir() if p.is_file()},
        "dependencies": {
            p: importlib.metadata.version(p)
            for p in [
                "numpy",
                "pandas",
                "scipy",
                "pyproj",
                "shapely",
                "matplotlib",
                "streamlit",
                "pyarrow",
            ]
        },
        "sample": {
            "gps_rows": len(gps),
            "vehicles": gps.vehicle_id.nunique(),
            "days": config["synthetic"]["days"],
            "truth_episodes": len(truth),
            "candidates": len(a.scores),
            "observation_type": "synthetic",
        },
        "stop_metrics": metrics,
        "public_data": public,
        "executed_experiments": {name: len(frame) for name, frame in tables.items()},
        "not_executed": [
            "independent_advertising_outcome_validation",
            "seasonal_generalization",
            "real_continuous_vehicle_GPS_validation",
        ],
    }
    write_report(out, a, tables, manifest)
    artifacts = [
        *out.joinpath("tables").glob("*.csv"),
        *figures,
        out / "RESEARCH_RESULTS.md",
        run / "grid_scores.geojson",
    ]
    manifest["artifacts"] = {str(p): sha256(p) for p in artifacts}
    write_json(run / "manifest.json", manifest)
    write_json(
        out / "runs/latest.json",
        {"run_id": run_id, "manifest": str(run / "manifest.json")},
    )
    # Retain numerical evidence per run, independent of later overwrite of presentation tables.
    (run / "tables").mkdir(exist_ok=True)
    for path in out.joinpath("tables").glob("*.csv"):
        shutil.copy2(path, run / "tables" / path.name)
    print(f"Completed run {run_id}; evidence: {out}/RESEARCH_RESULTS.md", flush=True)
    return manifest


def write_report(out, a, t, manifest):
    m = manifest["stop_metrics"]
    sample = manifest["sample"]
    comparison = t["model_comparison"]
    pair = comparison[
        (comparison.model_a == "static") & (comparison.model_b == "integrated")
    ].iloc[0]
    robustness = t["robustness"]
    worst = robustness.sort_values("f1").iloc[0]
    bootstrap = t["selection_stability"]
    public = manifest["public_data"]
    weights = t["weight_sensitivity"]
    strong = bootstrap[bootstrap.selection_probability >= 0.8]

    def f(x):
        return f"{x:.4f}" if x is not None and np.isfinite(x) else "NA"

    text = f"""# Transit OOH 연구 실험 결과

실행 ID: `{manifest["run_id"]}`. 결과는 실행된 코드에서 자동 작성했다. 원본 입력·코드·의존성 해시는 해당 실행의 manifest에 기록한다.

## 연구 목적과 자료 구분

기존 배송활동의 위치·시간 정보를 추가했을 때 후보지 선정과 안정성이 어떻게 달라지는지 분석한다. 광고효과·주목도·매출·정확도 향상은 검증하지 않았다.

주 실험: **synthetic** GPS {sample["gps_rows"]:,}개, {sample["vehicles"]}대, {sample["days"]}일, 독립 스케줄 GT 정차 {sample["truth_episodes"]}개, 동일 후보군 {sample["candidates"]}개. 실제 서울 배송 실증이 아니다. 좌표는 서울 범위지만 궤적·공간값 모두 합성이다. 모델 점수는 `assumed_decision_index`, 구간별 존재시간은 `estimated` 직선 보간이다.

## RQ1 — 시간·공간 분석의 검증

- 탐지 정차 {m["predicted_episodes"]}개, TP {m["tp"]}, FP {m["fp"]}, FN {m["fn"]}.
- Episode precision {f(m["precision"])}, recall {f(m["recall"])}, F1 {f(m["f1"])}. 차량 내 1:1 시간 IoU≥0.5 매칭이다.
- 매칭된 episode 정차시간 MAE {f(m["matched_duration_mae_seconds"])}초. 매칭 실패는 이 MAE에서 제외되므로 F1과 함께 해석한다.
- GT 총 정차시간 {m["true_dwell_seconds"] / 60:.2f}분, 추정 {m["predicted_dwell_seconds"] / 60:.2f}분, 오차 {m["total_dwell_error_seconds"] / 60:+.2f}분.
- 정차 목적 분류기는 없다. 배송 정차와 긴 신호·주차를 GPS만으로 구분했다고 주장하지 않는다.

근거: [stop_validation.csv](tables/stop_validation.csv), [quality.csv](tables/quality.csv), [정차 실패 그림](figures/stop_detection_failure_cases.png).

## RQ2 — 이동정보 추가의 의사결정 영향

동일 후보군 Static-only와 Integrated 순위 Spearman={f(pair.spearman)}, Kendall={f(pair.kendall)}, Top-{int(pair.top_k)} overlap={f(pair.top_k_overlap)}. 가중치 α={manifest["config"]["mobility_weight"]:g}은 사전적 초기 설정이다. 순위 변화는 산식에 따른 결과이며 정확도나 우월성의 증거가 아니다.

새 Mobility는 정규화한 비정차 구간 존재시간·정차시간·정차 방문횟수의 평균이다. Static은 합성 인구 .7/POI .3이다. 레거시 .4 방문+.4 체류+.2 반복 및 .6M+.4S는 별도 보존한다. 반복방문은 방문횟수와 중복되므로 새 기본 점수에서 제외하고 상관/VIF와 제거 실험으로 진단했다. 상수·완전공선 특성의 VIF는 NA와 플래그로 표시한다.

이동정보는 정적 맥락이 비슷한 격자들의 실제 차량 접촉 차이를 구분하는 데 쓸 수 있다. 이 자료에서는 **시뮬레이터가 정의한 접촉 차이**만 확인했다. 장소의 실제 광고가치에 유용한지는 독립 관측이 필요하다.

근거: [모델 비교](tables/model_comparison.csv), [특성 제거](tables/ablation.csv), [공선성](tables/feature_correlations.csv), [점수 기여도](figures/model_comparison_contributions.png).

## RQ3 — 선정 안정성과 실패 조건

- 가중치 α∈[0,1] 11개 실험에서 기준 대비 Top-K overlap 범위 {weights.top_k_overlap.min():.2f}–{weights.top_k_overlap.max():.2f}.
- 차량 전체 관측일을 묶은 cluster bootstrap {len(t["bootstrap_replicates"])}회; 선정확률≥0.8인 후보 {len(strong)}개. 점수 분위수는 현재 합성 설계에 조건부인 안정성 범위이며 도시 모집단의 신뢰구간이 아니다. {sample["vehicles"]}개 차량 cluster의 작은 유효 표본수를 유의해야 한다.
- 이동특성 벡터를 통째로 다른 격자에 배치하는 placebo {len(t["placebo"])}회로 특성 간 공분산을 보존했다. 광고 라벨이 없어 유의확률·예측정확도 검증으로 해석하지 않는다.
- 노이즈·표본주기·차량수·관측일수·불규칙/누락 {len(robustness)}개 실행. 가장 낮은 F1={worst.f1:.3f} (noise={worst.noise_m:g}m, sampling={worst.sample_seconds:g}s, seed={int(worst.seed)}). 최대 연결 간격 180초보다 드문 300초 표본은 연결하지 않아 정차를 놓칠 수 있다. 통과한 것처럼 숨기지 않았다.
- 100/200/400m 격자와 50/100m 원점 이동을 비교했다. 크기가 다른 격자 ID를 억지로 비교하지 않고 고정 200m 중심점의 공통 지지영역에서 점수를 비교한다. 경계에서 제외된 후보 수는 표에 드러난다.
- 기간·차량·오전/오후 holdout: 훈련 표본의 차량-일당 활동과 min–max 범위를 고정하고 동일 후보들의 순위 안정성을 비교. 공간 holdout: 서쪽에서 정규화, 동쪽 내부에서 두 모델 비교. 계절 검증은 다계절 실측이 없어 **미실행**.

근거: [robustness.csv](tables/robustness.csv), [holdout.csv](tables/holdout.csv), [선정확률](tables/selection_stability.csv), [격자](tables/grid_sensitivity.csv), [탐지 기준](tables/detector_sensitivity.csv).

## 실제 공개 자료 — 별도 기술통계

```json
{json.dumps(public, indent=2, ensure_ascii=False)}
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
"""
    (out / "RESEARCH_RESULTS.md").write_text(text, encoding="utf-8")
