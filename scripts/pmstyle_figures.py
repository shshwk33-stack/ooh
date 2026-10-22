"""Render presentation charts from hash-checked acquired public-study tables.

These figures re-express existing results. They do not rerun, alter, or select
the research model, and never interpret aggregate context as advertising effects.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd
from matplotlib import font_manager
from matplotlib.ticker import FuncFormatter, MultipleLocator

ORANGE = "#FF6F40"
TEAL = "#0E9384"
BLUE = "#3A5BA0"
GRAY = "#9CA5B6"
TEXT = "#16233A"
GRID = "#E9EDF2"
MODELS = {
    "A_stores": ("상권 단독 A", BLUE),
    "B_vehicle_context": ("교통 단독 B", GRAY),
    "C50_reduced": ("고정 50:50 C", ORANGE),
    "R_minimax": ("강건 선택 R", TEAL),
}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def configure():
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    font_path = Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
    if not font_path.is_file():
        raise FileNotFoundError(
            "Noto CJK font is required for Korean presentation charts"
        )
    font_manager.fontManager.addfont(font_path)
    plt.rcParams.update(
        {
            "font.family": font_manager.FontProperties(fname=font_path).get_name(),
            "font.size": 18,
            "axes.labelsize": 20,
            "axes.labelcolor": TEXT,
            "axes.edgecolor": GRAY,
            "axes.linewidth": 0.8,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.titlecolor": TEXT,
            "axes.unicode_minus": False,
            "xtick.labelsize": 18,
            "ytick.labelsize": 18,
            "xtick.color": TEXT,
            "ytick.color": TEXT,
            "text.color": TEXT,
            "legend.fontsize": 18,
            "legend.frameon": False,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "savefig.facecolor": "white",
            "svg.fonttype": "path",
        }
    )
    return plt, font_path


def style(ax, axis="y"):
    ax.set_axisbelow(True)
    ax.grid(axis=axis, color=GRID, linewidth=0.8)
    ax.tick_params(length=0, pad=9)
    ax.xaxis.labelpad = 13
    ax.yaxis.labelpad = 12


def checked_tables(report):
    manifest_path = report / "summary.json"
    summary = json.loads(manifest_path.read_text())
    names = [
        "nominal_scores",
        "portfolio_comparison",
        "all_portfolios_tradeoff",
        "price_of_robustness",
        "external_context_association",
    ]
    tables, sources = {}, {"summary.json": sha256(manifest_path)}
    for name in names:
        relative = f"tables/{name}.csv"
        path = report / relative
        actual = sha256(path)
        if actual != summary["artifacts_sha256"].get(relative):
            raise ValueError(f"Research artifact checksum mismatch: {relative}")
        tables[name] = pd.read_csv(path, dtype={"grid_id": str})
        sources[relative] = actual
    if summary["study_type"] != "acquired_aggregate_reduced_model_decision_study":
        raise ValueError("Presentation requires the acquired-data study")
    if summary["primary_k"] != 5:
        raise ValueError("Presentation charts are specified for the K=5 primary study")
    return summary, tables, sources


def numeric(frame, columns, unit=False):
    values = frame[columns].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("Plotting nonfinite or negative research values is forbidden")
    if unit and (values > 1).any():
        raise ValueError("Normalized research values exceed one")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=Path("reports/public_decision"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("deliverables/competition2026_pmstyle/assets"),
    )
    args = parser.parse_args()
    summary, tables, source_hashes = checked_tables(args.report)
    args.output.mkdir(parents=True, exist_ok=True)
    plt, font_path = configure()
    outputs, plot_data = {}, {}

    def save(fig, name, records, caption):
        fig.canvas.draw()
        for suffix in ["png", "svg"]:
            path = args.output / f"{name}.{suffix}"
            fig.savefig(path, dpi=180, bbox_inches="tight", pad_inches=0.15)
            if suffix == "svg":
                # Matplotlib emits spaces at path-line ends; retain all geometry.
                path.write_text(
                    "\n".join(line.rstrip() for line in path.read_text().splitlines())
                    + "\n"
                )
            outputs[path.name] = {"bytes": path.stat().st_size, "sha256": sha256(path)}
        plt.close(fig)
        plot_data[name] = {"caption": caption, "rows": records}

    nominal = tables["nominal_scores"].sort_values("grid_id").reset_index(drop=True)
    numeric(nominal, ["static_score", "mobility_score", "integrated_score"], unit=True)
    if nominal.grid_id.duplicated().any() or len(nominal) != summary["eligible_dongs"]:
        raise ValueError("Candidate support changed")
    comparisons = tables["portfolio_comparison"]
    primary = comparisons[
        (comparisons.k == 5)
        & (comparisons.weight_low == 0)
        & (comparisons.weight_high == 1)
    ]
    robust_rows = primary[primary.model.eq("R_minimax")]
    if len(robust_rows) != 1:
        raise ValueError("Require one fixed representative robust selection")
    selected = set(robust_rows.iloc[0].selected_ids.split(";"))
    if len(selected) != 5 or not selected <= set(nominal.grid_id):
        raise ValueError("Fixed selected candidate support differs")
    nominal["robust_selected"] = nominal.grid_id.isin(selected)

    # Point positions remain unmodified. Short leaders keep all fifteen names
    # readable even though most observed spatial scores cluster close to zero.
    fig, ax = plt.subplots(figsize=(9, 5.5), layout="constrained")
    style(ax, "both")
    ax.scatter(nominal.static_score, nominal.mobility_score, s=75, color=BLUE, zorder=3)
    selected_rows = nominal[nominal.robust_selected]
    ax.scatter(
        selected_rows.static_score,
        selected_rows.mobility_score,
        s=200,
        facecolors="none",
        edgecolors=ORANGE,
        linewidths=2.4,
        zorder=4,
        label="강건 선택 5곳",
    )
    offsets = {
        "용강동": (-41, -17),
        "공덕동": (13, 0),
        "성산2동": (-48, 8),
        "아현동": (-12, 13),
        "도화동": (8, -16),
        "성산1동": (-55, 1),
        "대흥동": (-43, -12),
        "서강동": (10, -7),
        "상암동": (10, 2),
        "서교동": (-12, 13),
        "망원1동": (8, 5),
        "연남동": (8, 8),
    }
    for row in nominal.itertuples():
        offset = offsets.get(row.name, (9, 8))
        ax.annotate(
            row.name,
            (row.static_score, row.mobility_score),
            xytext=offset,
            textcoords="offset points",
            fontsize=12.5,
            color=TEXT,
            fontweight="normal",
            arrowprops={"arrowstyle": "-", "color": GRAY, "linewidth": 0.65},
            zorder=5,
        )
    ax.set(
        xlim=(-0.14, 1.09),
        ylim=(-0.055, 1.10),
        xlabel="상권 점수 A",
        ylabel="차량 맥락 점수 B",
    )
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1])
    ax.set_yticks([0, 0.25, 0.5, 0.75, 1])
    ax.legend(loc="upper right", fontsize=18, markerscale=0.8)
    save(
        fig,
        "pm_candidate_tradeoff",
        nominal.to_dict("records"),
        "2024년 실제 집계·추정 맥락의 정규화 점수. 주황 테두리는 동점 중 코드순 대표 R 집합. 실제 정차·광고 노출 점수가 아님.",
    )

    portfolios = tables["all_portfolios_tradeoff"]
    numeric(portfolios, ["nominal_mean_utility", "worst_regret"], unit=True)
    if len(portfolios) != summary["combinations_evaluated"]:
        raise ValueError("Incomplete portfolio enumeration")
    if not portfolios.pareto_representative.isin([True, False]).all():
        raise ValueError("Invalid Pareto marker")
    frontier = portfolios[portfolios.pareto_representative].sort_values(
        "nominal_mean_utility"
    )
    price = tables["price_of_robustness"]
    numeric(
        price,
        ["nominal_mean_utility", "worst_regret", "nominal_loss_vs_C50"],
        unit=True,
    )
    fig, ax = plt.subplots(figsize=(9, 5.5), layout="constrained")
    style(ax)
    ax.scatter(
        portfolios.nominal_mean_utility,
        portfolios.worst_regret,
        s=12,
        color=GRAY,
        alpha=0.28,
        edgecolors="none",
        label=f"전체 {len(portfolios):,}개 조합",
        rasterized=True,
    )
    ax.plot(
        frontier.nominal_mean_utility,
        frontier.worst_regret,
        color=TEAL,
        linewidth=2.6,
        marker="o",
        markersize=5,
        label="Pareto 경계",
        zorder=3,
    )
    for model, color, marker in [
        ("C50_reduced", ORANGE, "D"),
        ("R_minimax", TEAL, "o"),
    ]:
        rows = price[price.model.eq(model)]
        if len(rows) != 1:
            raise ValueError("Missing fixed-model robustness price")
        row = rows.iloc[0]
        ax.scatter(
            row.nominal_mean_utility,
            row.worst_regret,
            s=175,
            marker=marker,
            color=color,
            edgecolors="white",
            linewidths=1.5,
            label=MODELS[model][0],
            zorder=5,
        )
    ax.set(xlabel="기본 50:50의 평균 효용  →", ylabel="최악후회  ·  작을수록 좋음")
    ax.set_ylim(0.17, portfolios.worst_regret.max() + 0.16)
    ax.legend(
        loc="upper left", ncol=2, fontsize=18, columnspacing=1.3, handletextpad=0.5
    )
    save(
        fig,
        "pm_portfolio_tradeoff",
        portfolios.to_dict("records"),
        "가능한 K=5 집합 3,003개. R은 최악후회를 줄이면서 명목 평균 효용 일부를 양보한다. 효용 차이는 광고손실액이나 비용절감률이 아님.",
    )

    sensitivity = comparisons[
        comparisons.model.isin(["C50_reduced", "R_minimax"])
    ].copy()
    numeric(sensitivity, ["worst_regret", "weight_low", "weight_high"], unit=True)
    fig, axes = plt.subplots(1, 2, figsize=(9, 5.5), sharey=True, layout="constrained")
    for ax, low, high, heading in zip(
        axes, [0.0, 0.3], [1.0, 0.7], ["가중치 0~100%", "가중치 30~70%"], strict=True
    ):
        style(ax)
        group = sensitivity[
            (sensitivity.weight_low == low) & (sensitivity.weight_high == high)
        ]
        for offset, model, color in [
            (-0.22, "C50_reduced", ORANGE),
            (0.22, "R_minimax", TEAL),
        ]:
            data = group[group.model.eq(model)].set_index("k").reindex([3, 5, 10])
            if len(data) != 3 or data.worst_regret.isna().any():
                raise ValueError("Incomplete K/range sensitivity support")
            bars = ax.bar(
                np.arange(3) + offset,
                data.worst_regret,
                width=0.36,
                color=color,
                label=MODELS[model][0],
                zorder=3,
            )
            ax.bar_label(
                bars,
                labels=[f"{value:.3f}" for value in data.worst_regret],
                fontsize=15,
                padding=5,
                color=TEXT,
            )
        ax.set_title(heading, fontsize=19, pad=16, fontweight="normal")
        ax.set_xticks([0, 1, 2], ["3", "5", "10"])
        ax.set_xlabel("선정 지역 수 K", fontsize=18)
        ax.set_ylim(0, 0.365)
        ax.yaxis.set_major_locator(MultipleLocator(0.1))
    axes[0].set_ylabel("최악후회", fontsize=20)
    axes[1].legend(loc="upper right", fontsize=18, handlelength=1.0, borderaxespad=0)
    save(
        fig,
        "pm_sensitivity",
        sensitivity.to_dict("records"),
        "같은 후보 수·같은 선호 범위에서 비교. 전체 가중치 범위 K=3에서는 C50과 R의 최악후회가 같다. 모든 조건의 엄격한 개선을 주장하지 않음.",
    )

    external = tables["external_context_association"]
    numeric(external, ["selected_transaction_share"], unit=True)
    expected_quarters = [20251, 20252, 20253, 20254]
    c50_external = external[external.model.eq("C50_reduced")].sort_values("quarter")
    c60_external = external[external.model.eq("C60_reduced")].sort_values("quarter")
    if not np.allclose(
        c50_external.selected_transaction_share,
        c60_external.selected_transaction_share,
        rtol=0,
        atol=1e-12,
    ):
        raise ValueError("C60 differs from C50; the shared-line caption would be false")
    fig, ax = plt.subplots(figsize=(9, 5.5), layout="constrained")
    style(ax)
    for model, (label, color) in MODELS.items():
        group = external[external.model.eq(model)].sort_values("quarter")
        if (
            group.quarter.tolist() != expected_quarters
            or not group.k.eq(5).all()
            or not group.eligible_dongs.eq(summary["eligible_dongs"]).all()
        ):
            raise ValueError(
                "External context must retain four quarters and the fixed K=5 support"
            )
        ax.plot(
            np.arange(4),
            group.selected_transaction_share,
            color=color,
            linewidth=2.8,
            marker="o",
            markersize=7,
            label=label,
            zorder=3,
        )
        last = group.iloc[-1].selected_transaction_share
        ax.annotate(
            f"{last:.1%}",
            (3, last),
            xytext=(12, 0),
            textcoords="offset points",
            color=color,
            fontsize=16,
            va="center",
            fontweight="normal",
        )
    ax.set_xticks([0, 1, 2, 3], ["2025 Q1", "Q2", "Q3", "Q4"])
    ax.set(
        xlim=(-0.12, 3.65),
        ylim=(0.15, 0.78),
        xlabel="2025년 분기",
        ylabel="선택 5개 동의 보고 거래 비중",
    )
    ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:.0%}"))
    ax.yaxis.set_major_locator(MultipleLocator(0.1))
    ax.legend(loc="upper center", ncol=2, fontsize=18, columnspacing=1.7)
    external_plot = external[external.model.isin(MODELS)].copy()
    save(
        fig,
        "pm_external_all_quarters",
        external_plot[
            [
                "quarter",
                "model",
                "k",
                "eligible_dongs",
                "selected_transaction_share",
                "target",
            ]
        ].to_dict("records"),
        "2025년 추정 거래의 회고적·탐색적 관련성. 분모는 비교 가능한 15개 동이며 광고효과 정답이 아님. C60은 C50과 선택 거래 비중이 같아 같은 선으로 표시. R에 후보별 순위상관을 부여하지 않음.",
    )

    manifest = {
        "created_at_utc": datetime.now(UTC).isoformat(),
        "data_type": summary["study_type"],
        "input_directory": str(args.report),
        "input_sha256": source_hashes,
        "generator_sha256": sha256(Path(__file__)),
        "font": str(font_path),
        "palette": {
            "orange": ORANGE,
            "teal": TEAL,
            "blue": BLUE,
            "gray": GRAY,
            "text": TEXT,
        },
        "research_tables_modified": False,
        "output_sha256": outputs,
        "plot_data": plot_data,
    }
    path = args.output / "figures_manifest.json"
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )
    print(
        json.dumps(
            {
                "output_directory": str(args.output),
                "figures": list(outputs),
                "manifest": str(path),
                "bytes": sum(row["bytes"] for row in outputs.values()),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
