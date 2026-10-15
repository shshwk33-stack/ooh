"""Stability of reported population-flow ranks, using actual day queries only."""

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd
from matplotlib import font_manager
from scipy.stats import spearmanr

from transit_ooh.viewt_population import (
    combine_inflow_batches,
    daily_inflow_panel,
    load_population,
    population_rank_stability,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="data/processed/viewt_population")
    parser.add_argument("--output", default="data/processed/viewt_acquired_report")
    parser.add_argument("--minimum-days", type=int, default=20)
    args = parser.parse_args()
    data = load_population(args.input)
    annual = combine_inflow_batches(
        [
            d
            for d in data
            if d[2]["kind"] == "inflow"
            and d[2]["destination_unit"] == "dong"
            and d[2]["requested_days"] == 262
        ]
    )
    panel = daily_inflow_panel(data, set(annual.destination_id))
    if panel.date.nunique() < args.minimum_days:
        raise ValueError("Actual complete daily sample is shorter than required")
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    results, draws = [], []
    for cluster in ["day", "week"]:
        result, replicates = population_rank_stability(
            panel, cluster=cluster, n=1000, seed=42
        )
        results.append(result)
        draws.append(replicates)
    stability = pd.concat(results, ignore_index=True)
    names = (
        annual[["destination_id", "destination_name"]]
        .drop_duplicates()
        .set_index("destination_id")
        .destination_name
    )
    stability["name"] = stability.destination_id.map(names).str.replace(
        "서울특별시 마포구 ", "", regex=False
    )
    stability.to_csv(
        out / "population_rank_stability.csv", index=False, encoding="utf-8-sig"
    )
    panel.to_csv(out / "actual_daily_inflow.csv", index=False, encoding="utf-8-sig")
    pd.concat(draws, ignore_index=True).to_csv(
        out / "population_bootstrap_draws.csv", index=False, encoding="utf-8-sig"
    )
    dates = sorted(panel.date.unique())
    source_manifest = json.loads((Path(args.input) / "manifest.json").read_text())
    coverage = source_manifest.get("daily_coverage")
    if coverage and set(coverage["planned_dates"]) - set(dates) != set(
        coverage["missing_dates"]
    ):
        raise ValueError("Coverage ledger and actual daily sample differ")
    middle = len(dates) // 2
    a = (
        panel[panel.date.isin(dates[:middle])]
        .groupby("destination_id")
        .reported_trips.mean()
        .sort_index()
    )
    b = (
        panel[panel.date.isin(dates[middle:])]
        .groupby("destination_id")
        .reported_trips.mean()
        .reindex(a.index)
    )
    overlaps = {
        str(k): len(
            set(a.sort_values(ascending=False, kind="stable").head(k).index)
            & set(b.sort_values(ascending=False, kind="stable").head(k).index)
        )
        / k
        for k in [5, 10]
    }
    summary = {
        "sample_start": dates[0],
        "sample_end": dates[-1],
        "days": len(dates),
        "planned_dates": coverage["planned_dates"] if coverage else dates,
        "missing_dates": coverage["missing_dates"] if coverage else [],
        "candidate_count": panel.destination_id.nunique(),
        "day_units": int(stability.query("method=='day'").resampling_units.iloc[0]),
        "week_units": int(stability.query("method=='week'").resampling_units.iloc[0]),
        "replicates_per_method": 1000,
        "seed": 42,
        "first_half_last_half_spearman": float(spearmanr(a, b).statistic),
        "first_half_last_half_top_k_overlap": overlaps,
        "distinct_daily_totals": int(
            panel.groupby("date").reported_trips.sum().nunique()
        ),
        "source_manifest_sha256": hashlib.sha256(
            (Path(args.input) / "manifest.json").read_bytes()
        ).hexdigest(),
        "interpretation": "Descriptive rank stability of reported estimated population flows. Not model accuracy, GPS or advertising exposure.",
        "limitations": [
            "Only four December weeks; not annual or seasonal representativeness.",
            "Day bootstrap assumes exchangeable days; whole-week bootstrap preserves within-week dependence but has only four clusters.",
            "Provider missing/suppressed O/D coverage is not independently certified. No absent candidate/date is filled with zero.",
        ],
    }
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    font = Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
    if font.exists():
        font_manager.fontManager.addfont(font)
        plt.rcParams["font.family"] = font_manager.FontProperties(fname=font).get_name()
    plt.rcParams.update(
        {
            "figure.dpi": 130,
            "savefig.dpi": 180,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "font.size": 10,
            "axes.unicode_minus": False,
        }
    )

    def save(fig, name):
        fig.text(
            0.02,
            0.015,
            f"KTDB View-T | {dates[0]}~{dates[-1]} 평일 {len(dates)}일 직접 조회 | 통합모델 성능·광고 효과 검증 아님",
            fontsize=8,
            color="#5b6470",
        )
        fig.tight_layout(rect=[0, 0.06, 1, 1])
        for ext in ["png", "svg"]:
            fig.savefig(out / (name + "." + ext), facecolor="white")
        plt.close(fig)

    t = stability.query("method=='day'").sort_values("mean_reported_trips")
    w = (
        stability.query("method=='week'")
        .set_index("destination_id")
        .reindex(t.destination_id)
    )
    fig, ax = plt.subplots(figsize=(10, 7))
    positions = np.arange(len(t))
    ax.barh(
        positions - 0.18,
        t.top5_probability * 100,
        height=0.35,
        label="일 단위 재표집",
        color="#14859c",
    )
    ax.barh(
        positions + 0.18,
        w.top5_probability * 100,
        height=0.35,
        label="주 단위 재표집 (4개 주)",
        color="#ef9f35",
    )
    ax.set_yticks(positions, t.name)
    ax.set(
        xlim=(0, 102),
        title="유입 통행량 상위 5개 동의 선정 빈도",
        xlabel="Bootstrap 1,000회에서 Top-5에 포함된 비율 (%)",
    )
    ax.legend()
    save(fig, "population_top5_stability")
    totals = panel.groupby("date").reported_trips.sum()
    fig, ax = plt.subplots(figsize=(11, 4.8))
    ax.plot(range(len(totals)), totals / 1000, marker="o", color="#14859c")
    ax.set_xticks(range(len(totals)), [d[5:] for d in totals.index], rotation=45)
    ax.set(
        title="실제 날짜별 요청으로 받은 마포구 유입 통행량",
        xlabel="2024년 12월 요청일",
        ylabel="반환 통행량 합계 (천 통행)",
    )
    ax.grid(alpha=0.15)
    save(fig, "actual_daily_inflow")
    summary["artifacts_sha256"] = {
        name: hashlib.sha256((out / name).read_bytes()).hexdigest()
        for name in [
            "population_rank_stability.csv",
            "actual_daily_inflow.csv",
            "population_bootstrap_draws.csv",
            "population_top5_stability.png",
            "population_top5_stability.svg",
            "actual_daily_inflow.png",
            "actual_daily_inflow.svg",
        ]
    }
    (out / "daily_stability_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2)
    )
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
