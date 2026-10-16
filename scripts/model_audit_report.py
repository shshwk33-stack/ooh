"""Research release: acquired context and synthetic model audit stay separate."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd
from matplotlib import font_manager

from transit_ooh.io import sha256, write_json
from transit_ooh.route_context import summarize_route_context
from transit_ooh.viewt import analyze_bundle, demo_bundle
from transit_ooh.viewt_boundary import choropleth, load_boundary
from transit_ooh.viewt_roads import load_context
from transit_ooh.viewt_routes import load_routes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="reports/model_audit")
    parser.add_argument("--replicates", type=int, default=1000)
    args = parser.parse_args()
    out = Path(args.output)
    tables, figures = out / "tables", out / "figures"
    tables.mkdir(parents=True, exist_ok=True)
    figures.mkdir(exist_ok=True)
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    font = Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
    if font.exists():
        font_manager.fontManager.addfont(font)
        plt.rcParams["font.family"] = font_manager.FontProperties(fname=font).get_name()
    plt.rcParams.update(
        {
            "axes.unicode_minus": False,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "font.size": 10,
        }
    )

    def save(fig, name, source):
        # Reserve space so source/limitations never collide with axis labels.
        fig.get_layout_engine().set(rect=(0, 0.09, 1, 0.91))
        fig.text(0.02, 0.015, source, fontsize=8, color="#486071")
        for ext in ["png", "svg"]:
            path = figures / (name + "." + ext)
            fig.savefig(path, dpi=180, bbox_inches="tight")
            if ext == "svg":
                path.write_text(
                    "\n".join(line.rstrip() for line in path.read_text().splitlines())
                    + "\n"
                )
        plt.close(fig)

    # Retain default synthetic data/seed so new diagnostics audit the existing case.
    bundle = demo_bundle(days=14, seed=42)
    study = analyze_bundle(bundle, bootstrap_n=args.replicates)
    week = analyze_bundle(bundle, bootstrap_n=args.replicates, bootstrap_unit="week")
    for name, frame in study.items():
        frame.assign(input_observation_type="synthetic").to_csv(
            tables / ("SYNTHETIC_" + name + ".csv"), index=False, encoding="utf-8-sig"
        )
    for name in ["bootstrap_replicates", "selection_stability"]:
        week[name].assign(input_observation_type="synthetic").to_csv(
            tables / ("SYNTHETIC_week_" + name + ".csv"),
            index=False,
            encoding="utf-8-sig",
        )
    robust = study["robust_candidates"].sort_values("top5_weight_share")
    fig, ax = plt.subplots(figsize=(10, 6), layout="constrained")
    ax.barh(robust.grid_id.str[-2:], robust.top5_weight_share, color="#19869e")
    ax.set(
        title="가중치 전체 범위에서 Top-5에 포함되는 구간 | 합성 시나리오",
        xlabel="Mobility 가중치 0~100% 중 포함 구간의 비율",
        ylabel="합성 후보 ID",
        xlim=(0, 1.03),
    )
    save(
        fig,
        "SYNTHETIC_continuous_weight_robustness",
        "Transit OOH 합성 데이터 seed42 · 관측 확률/실제 마포구 순위/광고효과가 아님",
    )
    specification = study["specification_comparison"].query("top_k == 5")
    heat = specification.pivot(
        index="normalization",
        columns="population_weight_within_spatial",
        values="top_k_overlap",
    )
    fig, ax = plt.subplots(figsize=(9, 4), layout="constrained")
    im = ax.imshow(heat, cmap="YlGnBu", vmin=0, vmax=1, aspect="auto")
    ax.set(
        xticks=range(len(heat.columns)),
        xticklabels=[f"{x:.0%}" for x in heat.columns],
        yticks=range(len(heat)),
        yticklabels=heat.index,
        xlabel="Spatial 내부 인구통행 비중",
        title="산식 가정이 달라졌을 때 Top-5 중복률 | 합성 시나리오",
    )
    for (i, j), value in np.ndenumerate(heat.to_numpy()):
        ax.text(
            j,
            i,
            f"{value:.0%}",
            ha="center",
            va="center",
            color="white" if value > 0.6 else "#15354b",
        )
    fig.colorbar(im, ax=ax, label="기본 설정과 후보 중복 비율")
    save(
        fig,
        "SYNTHETIC_specification_robustness",
        "기준 α=.5, Spatial 인구/POI=.7/.3 · 같은 16개 합성 후보 · 성능 최적화 결과가 아님",
    )

    # Only acquired source artifacts are accepted below; fail if missing or stale.
    roads, _ = load_context("data/processed/viewt_official_roads")
    paths, geometry, route_meta = load_routes("data/processed/viewt_vehicle_paths")
    context = summarize_route_context(paths, geometry, route_meta, roads)
    context.to_csv(
        tables / "ACQUIRED_route_context.csv", index=False, encoding="utf-8-sig"
    )
    complete = context[context.status.eq("complete_context")]
    fig, ax = plt.subplots(figsize=(9, 5), layout="constrained")
    labels = {
        "11140740_11140680": "상암→합정",
        "11140680_11140770": "합정→공덕",
        "11140770_11140740": "공덕→상암",
    }
    for (leg, group), color in zip(
        complete.groupby("leg"), ["#1a819d", "#e48b47", "#7967ac"], strict=True
    ):
        ax.scatter(
            group.link_time_proxy_minutes,
            group.length_weighted_traffic_per_day,
            color=color,
            label=labels[leg],
            s=65,
        )
        for row in group.itertuples():
            ax.annotate(
                str(row.rank),
                (row.link_time_proxy_minutes, row.length_weighted_traffic_per_day),
                xytext=(4, 4),
                textcoords="offset points",
                fontsize=9,
            )
    ax.set(
        title="공식 대표경로의 시간 대리지표와 교통 맥락 | 실제 확보 자료",
        xlabel="Σ(지도 링크 길이 / 연평균 속도), 분 · 실측 소요시간 아님",
        ylabel="길이 가중 교통량, 대/일 · 고유 차량 수 아님",
    )
    ax.legend(title="숫자: 기관 경로 순위")
    save(
        fig,
        "ACQUIRED_route_context",
        f"출처: KTDB View-T, 2024년 평일 종일 · {len(complete)}/15개 경로만 완전한 맥락 · 배송 경로/주행 가능성 미검증",
    )

    boundary, boundary_meta = load_boundary("data/processed/viewt_boundaries")
    pop = pd.read_csv(
        "data/processed/viewt_acquired_report/dong_inflow_2024_weekdays.csv",
        dtype={"destination_id": str},
    )
    mapped = choropleth(boundary, pop, 2024)
    gdf = gpd.GeoDataFrame.from_features(mapped["features"], crs=4326).to_crs(5179)
    fig, ax = plt.subplots(figsize=(10, 7), layout="constrained")
    gdf.plot(
        column="daily_mean",
        cmap="YlGnBu",
        edgecolor="#6c8391",
        linewidth=0.8,
        legend=True,
        legend_kwds={"label": "요청일수로 나눈 평균 통행 횟수"},
        ax=ax,
    )
    for row in gdf.itertuples():
        pt = row.geometry.representative_point()
        dx, dy = {"염리동": (-220, -220), "아현동": (260, 230)}.get(row.name, (0, 0))
        ax.annotate(
            row.name,
            xy=(pt.x, pt.y),
            xytext=(pt.x + dx, pt.y + dy),
            ha="center",
            va="center",
            fontsize=8,
            arrowprops={"arrowstyle": "-", "color": "#486071", "lw": 0.7}
            if dx
            else None,
            bbox={"facecolor": "white", "alpha": 0.75, "edgecolor": "none", "pad": 1.5},
        )
    ax.set_title("2024년 마포구 동별 유입 통행 | 공식 동 코드·명칭 연결")
    ax.set_axis_off()
    save(
        fig,
        "ACQUIRED_mapo_2024_choropleth",
        "출처: KTDB View-T · 2024년 월~금 262일 요청 · 공식 웹 지도 경계(정밀도 미검증) · 인구수/광고 노출 아님",
    )

    comparisons = (
        study["model_comparison"]
        .query("model_a == 'static' and model_b == 'integrated' and top_k == 5")
        .iloc[0]
    )
    summary = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "synthetic": {
            "seed": 42,
            "days": 14,
            "candidates": 16,
            "bootstrap_replicates_each": args.replicates,
            "weight_intervals": len(study["weight_intervals"]),
            "pareto_candidates": int(study["robust_candidates"].pareto_efficient.sum()),
            "minimax_regret_candidates": study["robust_candidates"]
            .query("minimax_regret_choice")
            .grid_id.tolist(),
            "A_C_spearman": float(comparisons.spearman),
            "A_C_top5_overlap": float(comparisons.top_k_overlap),
            "top5_specification_overlap_min": float(specification.top_k_overlap.min()),
            "top5_specification_overlap_max": float(specification.top_k_overlap.max()),
            "week_blocks": int(week["bootstrap_replicates"].block_count.iloc[0]),
            "interpretation": "synthetic_decision_behavior_not_real_model_performance",
        },
        "acquired": {
            "road_context_unique_links": int(roads.table.link_id.nunique()),
            "route_unique_links": int(paths.link_id.nunique()),
            "route_links_with_context": len(
                set(paths.link_id) & set(roads.table.link_id)
            ),
            "complete_context_routes": len(complete),
            "total_routes": len(context),
            "missing_context_links": sorted(
                set(paths.link_id) - set(roads.table.link_id)
            ),
            "boundary_dongs": boundary_meta["rows"],
            "boundary_max_relative_area_difference": boundary_meta[
                "max_relative_area_difference"
            ],
            "boundary_scope": boundary_meta["use"],
        },
        "independent_field_evaluation": "not_executed_no_field_observations",
        "real_integrated_A_B_C": "not_executed_no_reviewed_joint_support_and_contemporaneous_POI",
        "source_hashes": {
            str(p): sha256(p)
            for p in [
                Path("data/processed/viewt_population/manifest.json"),
                Path("data/processed/viewt_official_roads/metadata.json"),
                Path("data/processed/viewt_vehicle_paths/metadata.json"),
                Path("data/processed/viewt_boundaries/metadata.json"),
            ]
        },
        "code_hashes": {
            str(p): sha256(p)
            for p in [
                Path("src/transit_ooh/decision.py"),
                Path("src/transit_ooh/viewt.py"),
                Path("src/transit_ooh/route_context.py"),
                Path("src/transit_ooh/viewt_boundary.py"),
                Path("scripts/model_audit_report.py"),
            ]
        },
    }
    summary["artifacts_sha256"] = {
        str(p.relative_to(out)): sha256(p)
        for p in [*tables.glob("*.csv"), *figures.glob("*")]
    }
    write_json(out / "summary.json", summary)
    print(
        json.dumps(
            {"synthetic": summary["synthetic"], "acquired": summary["acquired"]},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
