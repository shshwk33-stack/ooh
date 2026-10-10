"""Export inspectable aggregate-flow experiments with explicit source status."""

from __future__ import annotations

import hashlib
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .io import sha256, write_json
from .viewt import analyze_bundle, milk_run


def export_study(
    bundle, output="reports/viewt", alpha=0.5, hours=None, bootstrap_n=200
):
    out = Path(output)
    tables, figures = out / "tables", out / "figures"
    tables.mkdir(parents=True, exist_ok=True)
    figures.mkdir(exist_ok=True)
    results = analyze_bundle(bundle, alpha, hours, bootstrap_n=bootstrap_n)
    sorted_scores = results["scores"].sort_values(
        ["integrated_score", "grid_id"], ascending=[False, True]
    )
    hubs = sorted_scores.head(4).grid_id.tolist()
    route_status = "executed"
    try:
        results["milk_run"] = milk_run(bundle, hubs, hours=hours)
    except ValueError as e:
        route_status = str(e)
    for name, frame in results.items():
        frame = frame.copy()
        frame["input_observation_type"] = bundle.observation_type
        frame["score_type"] = "assumed_decision_index"
        frame.to_csv(tables / f"{name}.csv", index=False, encoding="utf-8-sig")
    artifacts = []

    def save(fig, name):
        fig.suptitle(
            f"{name.replace('_', ' ').title()} · {bundle.observation_type.upper()}",
            fontsize=12,
        )
        for ext in ["png", "svg"]:
            p = figures / f"{name}.{ext}"
            fig.savefig(p, dpi=180, bbox_inches="tight")
            artifacts.append(p)
        plt.close(fig)

    top = sorted_scores.head(10).sort_values("integrated_score")
    fig, ax = plt.subplots(figsize=(9, 5), layout="constrained")
    y = range(len(top))
    ax.barh(
        y,
        (1 - alpha) * top.static_score,
        label=f"Spatial × {1 - alpha:.2f}",
        color="#46a4ab",
    )
    ax.barh(
        y,
        alpha * top.mobility_score,
        left=(1 - alpha) * top.static_score,
        label=f"Mobility proxy × {alpha:.2f}",
        color="#253f6c",
    )
    ax.set(
        yticks=list(y),
        yticklabels=top.grid_id,
        xlabel="Relative decision index (not advertising exposure)",
    )
    ax.legend(loc="lower right")
    save(fig, "model_contributions")
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), layout="constrained")
    for k, group in results["weight_sensitivity"].groupby("top_k"):
        axes[0].plot(
            group.mobility_weight,
            group.top_k_overlap,
            marker="o",
            ms=3,
            label=f"Top-{k}",
        )
    axes[0].set(
        xlabel="Mobility weight",
        ylabel="Overlap with current selection",
        ylim=(-0.03, 1.05),
    )
    axes[0].legend()
    w = results["weight_sensitivity"].drop_duplicates("mobility_weight")
    axes[1].plot(w.mobility_weight, w.spearman, color="#253f6c")
    axes[1].set(
        xlabel="Mobility weight",
        ylabel="Spearman vs current ranking",
        ylim=(-1.05, 1.05),
    )
    save(fig, "weight_sensitivity")
    fig, ax = plt.subplots(figsize=(9, 5), layout="constrained")
    for _zone, group in results["weight_ranks"].groupby("grid_id"):
        ax.plot(group.mobility_weight, group.integrated_rank, alpha=0.65, lw=1)
    ax.invert_yaxis()
    ax.set(xlabel="Mobility weight", ylabel="Rank (average ties)")
    save(fig, "rank_trajectories")
    stable = results["selection_stability"]
    if not stable.empty:
        fig, ax = plt.subplots(figsize=(9, 5), layout="constrained")
        stable = stable.sort_values("top5_probability")
        ax.barh(stable.grid_id, stable.top5_probability, color="#317e91")
        ax.set(
            xlabel=f"Top-5 frequency across {bootstrap_n} paired day resamples",
            xlim=(0, 1.05),
        )
        save(fig, "selection_stability")
    write_json(out / "input_metadata.json", bundle.metadata)
    manifest = {
        "input_observation_type": bundle.observation_type,
        "source_verification": "user_declared_metadata_not_provider_authentication",
        "viewt_live_acquisition": "not_acquired"
        if bundle.observation_type == "synthetic"
        else "user_supplied_files_not_authenticated_by_app",
        "alpha": alpha,
        "hours": hours or bundle.metadata["hours"],
        "bootstrap_n": bootstrap_n,
        "candidate_count": len(sorted_scores),
        "day_count": results["daily"].date.nunique(),
        "route_status": route_status,
        "unavailable": [
            "observed_milk_run_GPS",
            "GPS_dwell_from_aggregate",
            "advertising_outcome_validation",
            "optimal_weight_validation",
        ],
        "input_hashes": {
            name: hashlib.sha256(frame.to_csv(index=False).encode()).hexdigest()
            for name, frame in bundle.tables.items()
        },
        "metadata_sha256": sha256(out / "input_metadata.json"),
        "code_hashes": {
            str(p): sha256(p) for p in Path("src/transit_ooh").glob("*.py")
        },
        "artifacts": {str(p): sha256(p) for p in [*tables.glob("*.csv"), *artifacts]},
    }
    write_json(out / "manifest.json", manifest)
    comparison = results["model_comparison"]
    pair = comparison[
        (comparison.model_a == "static")
        & (comparison.model_b == "integrated")
        & (comparison.top_k == min(5, len(sorted_scores)))
    ].iloc[0]
    (out / "RESULTS.md").write_text(
        f"""# View-T 파일 연동 의사결정 실험

입력 분류: **{bundle.observation_type}**. View-T 공식 실자료 수집 여부: **{manifest["viewt_live_acquisition"]}**.
자치구 코드 {bundle.metadata["district_code"]}, 기간 {bundle.metadata["start_date"]}–{bundle.metadata["end_date"]}, 후보 {len(sorted_scores)}개, {manifest["day_count"]}일.

## 모델과 실험

A = .7 × 정규화 인구통행 + .3 × 정규화 POI. B = 정규화 차량 통행량 대리지표. C = αB + (1−α)A, 현재 α={alpha:.2f}.
기존 GPS 모델의 정차시간·방문횟수 산식은 별도 유지하며, 이 자료에서 그 지표는 측정 불가다. 인구 O/D는 목적지 유입, 통행구간 자료는 구역 통행량으로 해석한다. 둘을 합산하지 않는다. 통행량은 고유 인원·광고 노출이 아니다.

A–C 순위 Spearman={pair.spearman:.4f}, Top-{int(pair.top_k)} 중복률={pair.top_k_overlap:.4f}.
이는 의사결정 변화이며 성능 향상의 증거가 아니다. 50:50·60:40·0~100%를 같은 후보군/정규화에서 비교했다. 60:40은 과거 초기 가정이며 최적값이 아니다.

동일 일자를 인구·차량 자료에 함께 재표집하는 day-cluster Bootstrap {bootstrap_n}회. 일자가 3개 미만이면 미실행한다. 점수 범위는 조건부 안정성이며 광고효과 신뢰구간이 아니다. 연속일의 자기상관은 처리하지 않아 모집단 추론에 사용할 수 없다. POI는 고정하므로 통합 점수 안정성이 높아질 수 있어 Mobility 단독 상관도 제공한다.
시간 holdout은 훈련 구간 정규화만 사용하지만 독립 광고 라벨 검증은 아니다. 실제 검증은 고정된 관측 지점·시간의 별도 수동 차량/보행자 계수와 운행 동의 GPS를 확보한 뒤 수행해야 한다.

## 경로와 한계

가상 밀크런: {route_status}. 제공된 경로의 방향별 구역 인접관계 위에서 거점 순서를 반복한다. 도로 경로가 아닌 구역 중심 간 개략선이며 속도·정차시간은 가정이다. 도로별 속도, 화물차 여부, 실제 차량 ID는 이 파일 계약에 없으며 측정했다고 보고하지 않는다.
합성 기본 시나리오는 자치구 중심 부근의 가상 후보다. 공식 행정경계의 포함 여부를 인증하지 않으며 실제 분석에는 검토된 공간구역 코드 대응표가 필요하다.

표: `tables/` · 발표용 PNG/SVG: `figures/` · 출처/해시/실행 범위: `manifest.json`, `input_metadata.json`.
공식 사이트 접속 제한과 파일 준비 절차: `../../docs/VIEWT_DATA_GUIDE.md`.
""",
        encoding="utf-8",
    )
    return manifest
