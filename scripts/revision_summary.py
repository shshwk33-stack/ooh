"""Render the paired held-out detector audit from executed experiment tables."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from transit_ooh.io import sha256, write_json

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / "reports/tables/detector_benchmark.csv"
d = pd.read_csv(source)
out = ROOT / "reports/revision"
out.mkdir(exist_ok=True)
summary = d.groupby(["noise_m", "accuracy_mode", "method"], as_index=False).agg(
    mean_f1=("f1", "mean"), min_f1=("f1", "min"), experiments=("f1", "size")
)
summary.to_csv(out / "heldout_detector_summary.csv", index=False)
fig, axes = plt.subplots(1, 2, figsize=(11, 4), layout="constrained")
pivot = summary.pivot(
    index=["noise_m", "accuracy_mode"], columns="method", values="mean_f1"
)
pivot.plot.bar(ax=axes[0], color=["#a9b2c2", "#237d8c"], rot=20)
axes[0].set(
    xlabel="Noise SD / supplied accuracy",
    ylabel="Mean episode F1",
    ylim=(0, 1.08),
    title="Fixed thresholds; held-out synthetic schedules",
)
paired = d.pivot(
    index=["scenario_seed", "schedule", "noise_m", "accuracy_mode"],
    columns="method",
    values="f1",
)
axes[1].scatter(paired.anchor, paired.robust, color="#237d8c", alpha=0.75)
axes[1].plot([0, 1], [0, 1], "--", color="grey")
axes[1].set(
    xlabel="Anchor F1",
    ylabel="Robust F1",
    xlim=(0, 1.03),
    ylim=(0, 1.03),
    title="Same GPS / GT in each paired comparison",
)
fig.suptitle(
    "SYNTHETIC · Accuracy missing at 35m remains a failure condition", fontsize=12
)
for ext in ["png", "svg"]:
    fig.savefig(
        out / ("heldout_detector_comparison." + ext), dpi=180, bbox_inches="tight"
    )
plt.close(fig)
write_json(
    out / "manifest.json",
    {
        "observation_type": "synthetic",
        "input": str(source.relative_to(ROOT)),
        "input_sha256": sha256(source),
        "run_ids": d.run_id.unique().tolist(),
        "threshold_selection": "fixed_before_this_benchmark",
        "experiments": len(d),
        "artifacts": {
            str(p.relative_to(ROOT)): sha256(p)
            for p in out.iterdir()
            if p.suffix in {".png", ".svg", ".csv"}
        },
    },
)
print(summary.to_string(index=False))
