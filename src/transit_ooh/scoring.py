"""Transparent decision indices, never fitted advertising-effect predictions."""

from __future__ import annotations
import numpy as np
import pandas as pd
from scipy.stats import spearmanr, kendalltau

NEW_FEATURES = ["moving_seconds", "stop_seconds", "visit_frequency"]
LEGACY_FEATURES = ["visit_frequency", "total_dwell_minutes", "repeat_visits"]


class MinMax:
    def __init__(self):
        self.bounds = {}

    def fit(self, frame, features):
        self.bounds = {
            c: (float(frame[c].min()), float(frame[c].max()))
            for c in features
            if c in frame and frame[c].notna().any()
        }
        return self

    def transform(self, frame):
        out = pd.DataFrame(index=frame.index)
        for c, (lo, hi) in self.bounds.items():
            values = pd.to_numeric(frame[c], errors="raise").astype(float)
            out[c] = (
                ((values - lo) / (hi - lo)).clip(0, 1)
                if hi > lo
                else values.where(values.isna(), 0.0)
            )
        return out


def score(frame, alpha=0.6, normalizer=None, omit=None):
    if not 0 <= alpha <= 1:
        raise ValueError("Mobility weight must be within [0,1]")
    d = frame.copy()
    features = list(
        dict.fromkeys(NEW_FEATURES + LEGACY_FEATURES + ["population", "poi_count"])
    )
    norm = normalizer or MinMax().fit(d, features)
    z = norm.transform(d)
    active = [c for c in NEW_FEATURES if c != omit]
    d["mobility_score"] = z[active].mean(axis=1, skipna=False)
    spatial = [c for c in ["population", "poi_count"] if c in z]
    if not spatial:
        d["static_score"] = np.nan
    elif len(spatial) == 2:
        d["static_score"] = 0.7 * z.population + 0.3 * z.poi_count
    else:
        d["static_score"] = z[spatial[0]]
    d["legacy_mobility_score"] = (
        0.4 * z.visit_frequency + 0.4 * z.total_dwell_minutes + 0.2 * z.repeat_visits
    )
    # Historical baseline is fixed even when the new model's alpha is varied.
    d["legacy_integrated_score"] = 0.6 * d.legacy_mobility_score + 0.4 * d.static_score
    d["integrated_score"] = alpha * d.mobility_score + (1 - alpha) * d.static_score
    d["moving_contribution"] = (
        alpha * z.moving_seconds / len(active) if "moving_seconds" in active else 0.0
    )
    d["stop_contribution"] = (
        alpha * z.stop_seconds / len(active) if "stop_seconds" in active else 0.0
    )
    d["visit_contribution"] = (
        alpha * z.visit_frequency / len(active) if "visit_frequency" in active else 0.0
    )
    d["spatial_contribution"] = (1 - alpha) * d.static_score
    for c in ["static", "mobility", "integrated", "legacy_integrated"]:
        d[c + "_rank"] = d[c + "_score"].rank(method="average", ascending=False)
    return d, norm


def top_keys(frame, column="integrated_score", k=5):
    return set(
        frame.dropna(subset=[column])
        .sort_values([column, "grid_id"], ascending=[False, True])
        .head(k)
        .grid_id
    )


def rank_metrics(a, b, column_a="integrated_score", column_b="integrated_score", k=5):
    merged = (
        a[["grid_id", column_a]]
        .rename(columns={column_a: "a"})
        .merge(
            b[["grid_id", column_b]].rename(columns={column_b: "b"}),
            on="grid_id",
            validate="one_to_one",
        )
        .dropna()
    )
    n = len(merged)
    k = min(k, n)
    if n < 2 or merged.a.nunique() < 2 or merged.b.nunique() < 2:
        rho = tau = np.nan
    else:
        rho = float(
            spearmanr(
                merged.a.to_numpy(dtype=float), merged.b.to_numpy(dtype=float)
            ).statistic
        )
        tau = float(
            kendalltau(
                merged.a.to_numpy(dtype=float), merged.b.to_numpy(dtype=float)
            ).statistic
        )
    at = top_keys(merged.rename(columns={"a": "score"}), "score", k)
    bt = top_keys(merged.rename(columns={"b": "score"}), "score", k)
    return {
        "n_candidates": n,
        "spearman": rho,
        "kendall": tau,
        "top_k": k,
        "top_k_overlap": len(at & bt) / k if k else np.nan,
    }
