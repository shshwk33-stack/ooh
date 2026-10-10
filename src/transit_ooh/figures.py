"""Exportable research figures, with provenance labels in every figure."""

import os
import tempfile
from pathlib import Path

os.environ.setdefault(
    "XDG_CACHE_HOME", str(Path(tempfile.gettempdir()) / "transit-ooh-cache")
)
os.environ.setdefault(
    "MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "transit-ooh-mpl")
)
import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

plt.rcParams.update(
    {
        "figure.dpi": 130,
        "savefig.dpi": 160,
        "font.size": 10,
        "axes.spines.top": False,
        "axes.spines.right": False,
    }
)


def research_figures(analysis, truth, tables, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    files = []

    def save(fig, name, kind="synthetic"):
        fig.text(
            0.01,
            0.01,
            f"Data: {kind} | Relative decision indices, not advertising effectiveness",
            fontsize=8,
            color="#555",
        )
        fig.tight_layout(rect=[0, 0.045, 1, 1])
        for ext in ["png", "svg"]:
            path = out / f"{name}.{ext}"
            fig.savefig(path)
            files.append(path)
        plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 7))
    for (_v, _day), d in analysis.gps.groupby(
        ["vehicle_id", analysis.gps.timestamp.dt.date]
    ):
        ax.plot(d.x, d.y, alpha=0.22, lw=0.8)
    s = analysis.scores
    for row in s.itertuples():
        x0, y0, x1, y1 = analysis.grid.bounds(row.grid_id)
        ax.add_patch(
            Rectangle(
                (x0, y0),
                x1 - x0,
                y1 - y0,
                facecolor=plt.cm.YlOrRd(row.integrated_score),
                edgecolor="#aaa",
                alpha=0.35,
                lw=0.4,
            )
        )
    ax.scatter(
        analysis.stops.x,
        analysis.stops.y,
        s=18,
        c="#142d4e",
        label="Detected stop episode",
    )
    ax.set(
        xlabel="UTM 52N easting (m)",
        ylabel="UTM 52N northing (m)",
        title="Synthetic fixes, detected stops, and integrated score",
    )
    ax.set_aspect("equal")
    ax.legend()
    save(fig, "mobility_stop_map")
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    axes[0].scatter(
        s.static_rank, s.integrated_rank, c=s.mobility_score, cmap="viridis"
    )
    axes[0].plot([1, len(s)], [1, len(s)], "--", c="gray")
    axes[0].set(
        xlabel="Static rank (average ties)",
        ylabel="Integrated rank",
        title="Candidate changes; no accuracy label",
    )
    top = s.sort_values(["integrated_score", "grid_id"], ascending=[False, True]).head(
        5
    )
    bottom = np.zeros(len(top))
    for c, color in zip(
        [
            "moving_contribution",
            "stop_contribution",
            "visit_contribution",
            "spatial_contribution",
        ],
        ["#367ca5", "#1caa92", "#e8a048", "#243653"],
        strict=False,
    ):
        axes[1].bar(
            np.arange(len(top)),
            top[c],
            bottom=bottom,
            label=c.replace("_contribution", ""),
            color=color,
        )
        bottom += top[c].to_numpy()
    axes[1].set_xticks(np.arange(len(top)), top.grid_id, rotation=35, ha="right")
    axes[1].set(title="Top-5 score contributions", ylabel="Assumed index")
    axes[1].legend(fontsize=8, loc="upper left", ncol=2)
    axes[1].set_ylim(0, max(float(bottom.max()) * 1.35, 0.1))
    save(fig, "model_comparison_contributions")
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    w = tables["weight_sensitivity"]
    g = tables["grid_sensitivity"]
    axes[0].plot(w.mobility_weight, w.spearman, "o-", label="Spearman")
    axes[0].plot(w.mobility_weight, w.top_k_overlap, "s-", label="Top-5 overlap")
    axes[0].set(
        xlabel="Mobility weight",
        ylabel=f"Stability vs {analysis.mobility_weight:g}",
        title="Weight sensitivity",
    )
    axes[0].legend()
    axes[1].bar(np.arange(len(g)), g.top_k_overlap, color="#377e9d")
    axes[1].set_xticks(
        np.arange(len(g)),
        [f"{r.grid_size_m}m\nshift {r.origin_offset_m}m" for r in g.itertuples()],
    )
    axes[1].set(
        ylabel="Top-5 overlap on fixed anchors",
        title="Grid and boundary sensitivity",
        ylim=(0, 1.05),
    )
    save(fig, "weight_grid_sensitivity")
    r = tables["robustness"]
    subset = r[r.scenario == "sampling_noise"]
    pivot = subset.groupby(["noise_m", "sample_seconds"]).f1.mean().unstack()
    fig, ax = plt.subplots(figsize=(7, 4))
    im = ax.imshow(pivot, vmin=0, vmax=1, cmap="viridis", aspect="auto")
    ax.set_xticks(range(len(pivot.columns)), pivot.columns)
    ax.set_yticks(range(len(pivot.index)), pivot.index)
    ax.set(
        xlabel="Sampling interval (seconds)",
        ylabel="GPS noise SD (metres)",
        title="Stop episode F1, mean across seeds",
    )
    for i in range(len(pivot)):
        for j in range(len(pivot.columns)):
            ax.text(
                j,
                i,
                f"{pivot.iloc[i, j]:.2f}",
                ha="center",
                va="center",
                color="white" if pivot.iloc[i, j] < 0.6 else "black",
            )
    fig.colorbar(im, ax=ax, label="F1 (IoU >= 0.5)")
    save(fig, "noise_sampling_robustness")
    boot = (
        tables["selection_stability"]
        .sort_values("selection_probability", ascending=False)
        .head(12)
    )
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    axes[0].barh(
        boot.grid_id[::-1], boot.selection_probability.iloc[::-1], color="#227d83"
    )
    axes[0].set(
        xlabel="Top-5 selection frequency",
        title="Vehicle-cluster bootstrap (conditional)",
    )
    p = tables["placebo"]
    axes[1].hist(
        p.top_k_overlap,
        bins=np.linspace(-0.05, 1.05, 12),
        color="#688caf",
        edgecolor="white",
    )
    axes[1].set(
        xlabel="Top-5 overlap with baseline",
        ylabel="Permutation count",
        title="Joint mobility permutation placebo",
    )
    save(fig, "bootstrap_placebo")
    # Failure evidence is sourced from the actual robustness experiment, including zero detections.
    worst = subset.sort_values(["f1", "noise_m"], ascending=[True, False]).iloc[0]
    best = subset[(subset.noise_m == 5) & (subset.sample_seconds == 30)].iloc[0]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    labels = ["GT episodes", "TP", "FP", "FN"]
    for ax, row, label in [
        (axes[0], best, "Baseline scenario"),
        (axes[1], worst, "Failure scenario"),
    ]:
        ax.bar(
            labels,
            [row.true_episodes, row.tp, row.fp, row.fn],
            color=["#557f9b", "#239f83", "#cf6f5e", "#db9f51"],
        )
        ax.set_title(
            f"{label}\nnoise={row.noise_m:g}m, interval={row.sample_seconds:g}s"
        )
        ax.set_ylabel("Episodes")
    save(fig, "stop_detection_failure_cases")
    fig, ax = plt.subplots(figsize=(10, 3))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 2)
    ax.axis("off")
    labels = [
        "GPS + provenance",
        "QC + metric CRS",
        "Stop / moving time",
        "Spatial key join",
        "Compare + stress test",
        "GIS + report",
    ]
    for i, label in enumerate(labels):
        x = i * 1.65
        ax.add_patch(
            Rectangle((x, 0.7), 1.45, 0.6, facecolor="#edf3f7", edgecolor="#376981")
        )
        ax.text(x + 0.725, 1, label, ha="center", va="center", fontsize=8)
        if i < 5:
            ax.annotate(
                "",
                xy=(x + 1.65, 1),
                xytext=(x + 1.45, 1),
                arrowprops={"arrowstyle": "->"},
            )
    ax.set_title("Reproducible research workflow: real public studies remain separate")
    save(fig, "data_flow", "method diagram; synthetic and public_observed separated")
    return files


def public_figures(tables_dir, out):
    import pandas as pd

    root = Path(tables_dir)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    files = []
    for filename, x, y, title, attribution in [
        (
            "public_amazon_station_summary.csv",
            "station_code",
            "routes",
            "Amazon 2018 evaluation routes by station",
            "Amazon LMRRC · CC BY-NC 4.0",
        ),
        (
            "public_osm_amenity_summary.csv",
            "amenity",
            "mapped_nodes",
            "Seoul OSM node amenities in bounded extract",
            "© OpenStreetMap contributors · ODbL-1.0",
        ),
    ]:
        p = root / filename
        if not p.exists():
            continue
        d = pd.read_csv(p).sort_values(y, ascending=False).head(15)
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.bar(d[x].astype(str), d[y], color="#276c83")
        ax.tick_params(axis="x", rotation=40)
        ax.set(title=title, ylabel="Count")
        fig.text(
            0.01,
            0.01,
            f"public_observed | {attribution}\nSeparate places/periods; no continuous GPS or ad-effect inference",
            fontsize=8,
        )
        fig.tight_layout(rect=[0, 0.09, 1, 1])
        for ext in ["png", "svg"]:
            dest = out / (Path(filename).stem + "." + ext)
            fig.savefig(dest)
            files.append(dest)
        plt.close(fig)
    monthly = root / "public_lade_monthly_stability.csv"
    stability = root / "public_lade_aoi_stability.csv"
    if monthly.exists() and stability.exists():
        d = pd.read_csv(monthly)
        s = pd.read_csv(stability)
        fig, axes = plt.subplots(1, 2, figsize=(11, 4))
        axes[0].plot(d.heldout_month, d.top_k_overlap, "o-", label="Top-10 overlap")
        axes[0].plot(d.heldout_month, d.spearman, "s-", label="Spearman")
        axes[0].set(
            xlabel="Following month (provider local dates, 2022)",
            ylabel="Stability",
            title="LaDe Jilin: adjacent-month AOI task counts",
        )
        axes[0].legend()
        axes[1].hist(
            s.top10_selection_probability,
            bins=np.linspace(0, 1, 11),
            color="#3b8b95",
            edgecolor="white",
        )
        axes[1].set(
            xlabel="Top-10 selection frequency",
            ylabel="Eligible AOIs",
            title="57-courier cluster bootstrap",
        )
        fig.text(
            0.01,
            0.01,
            "public_observed · LaDe-D Jilin · Wu et al., arXiv:2306.10675 (CC BY-NC 4.0 per paper)\nRecorded tasks/nearest GPS events; no vehicle-visit, dwell or advertising-outcome measurements",
            fontsize=8,
        )
        fig.tight_layout(rect=[0, 0.09, 1, 1])
        for ext in ["png", "svg"]:
            dest = out / f"public_lade_event_stability.{ext}"
            fig.savefig(dest)
            files.append(dest)
        plt.close(fig)
    return files
