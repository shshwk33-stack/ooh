"""Continuous two-criterion decision audit; preferences are not probabilities.

Linear scores can change order only at pairwise intersections. Examining every
open interval and boundary avoids missing a narrow optimum between grid samples.
No outcomes are used to choose weights. Equal scores use lexical candidate IDs
for operational selection, with separate tie-inclusive/exclusive bounds.
"""

from __future__ import annotations

from itertools import pairwise

import numpy as np
import pandas as pd

from .scoring import rank_metrics


def weight_audit(scores, low=0.0, high=1.0, ks=(5, 10)):
    """Audit C=alpha*B+(1-alpha)*A on a fixed candidate set and normalization.

    Weight shares are interval lengths under a uniform *preference scenario*,
    not empirical selection probabilities. All crossings are computed in float64.
    Minimax regret is exact for this linear family: convex regret attains its
    maximum at an endpoint. Endpoint-only ties have zero interval measure.
    """
    if not np.isfinite([low, high]).all() or not 0 <= low < high <= 1:
        raise ValueError("Require 0 <= low < high <= 1")
    cols = ["grid_id", "static_score", "mobility_score"]
    if not set(cols) <= set(scores):
        raise ValueError("Require candidate ID and both component scores")
    d = scores[cols].copy()
    if d.isna().any().any() or not 1 <= len(d) <= 500:
        raise ValueError("Require 1..500 complete candidates for continuous analysis")
    d["grid_id"] = d.grid_id.astype(str).str.strip()
    if d.grid_id.eq("").any() or d.grid_id.duplicated().any():
        raise ValueError("Unique nonempty candidate IDs required")
    d = d.sort_values("grid_id").reset_index(drop=True)
    values = d[["static_score", "mobility_score"]].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values < 0).any() or (values > 1).any():
        raise ValueError("Component scores must be finite within [0,1]")
    if not ks or any(
        isinstance(k, bool) or not isinstance(k, int) or k < 1 for k in ks
    ):
        raise ValueError("Positive integer Top-K values required")
    ks = tuple(sorted(set(ks)))
    a, b = values.T
    slope = b - a
    crossings = [float(low), float(high)]
    for i in range(len(d)):
        den = slope[i] - slope[i + 1 :]
        valid = den != 0
        roots = (a[i + 1 :][valid] - a[i]) / den[valid]
        crossings.extend(roots[(roots > low) & (roots < high)].tolist())
    edges = np.unique(crossings)
    # Tiny duplicate numerical roots have no meaningful preference interval.
    edges = np.r_[edges[0], edges[1:][np.diff(edges) > 8 * np.finfo(float).eps]]
    edges[-1] = high
    summary = d.copy()
    n = len(d)
    best, worst = np.full(n, n, dtype=int), np.ones(n, dtype=int)
    shares = {k: np.zeros((n, 3)) for k in ks}
    segments, boundary_rows = [], []

    def ranks(alpha):
        value = a + alpha * slope
        # Roundoff at analytical intersections must not create false strict ranks.
        rounded = np.round(value, 14)
        ordered = np.sort(-rounded)
        higher = np.searchsorted(ordered, -rounded, side="left")
        equal_or_higher = np.searchsorted(ordered, -rounded, side="right")
        order = np.lexsort((d.grid_id.to_numpy(), -rounded))
        deterministic = np.empty(n, dtype=int)
        deterministic[order] = np.arange(1, n + 1)
        return value, higher + 1, equal_or_higher, deterministic

    for left, right in pairwise(edges):
        alpha = (left + right) / 2
        _, rmin, rmax, deterministic = ranks(alpha)
        best, worst = np.minimum(best, rmin), np.maximum(worst, rmax)
        width = (right - left) / (high - low)
        for k in ks:
            cutoff = min(k, n)
            shares[k] += width * np.column_stack(
                [deterministic <= cutoff, rmax <= cutoff, rmin <= cutoff]
            )
        record = {"alpha_low": left, "alpha_high": right, "alpha_mid": alpha}
        for k in ks:
            record[f"top{k}_ids"] = ";".join(
                d.loc[deterministic <= min(k, n), "grid_id"]
            )
        record["winner_ids"] = ";".join(d.loc[rmin == 1, "grid_id"])
        segments.append(record)
    for edge in edges:
        _, rmin, rmax, _ = ranks(edge)
        best, worst = np.minimum(best, rmin), np.maximum(worst, rmax)
        boundary_rows.append(
            {"alpha": edge, "winner_ids": ";".join(d.loc[rmin == 1, "grid_id"])}
        )
    summary["best_possible_rank"] = best
    summary["worst_possible_rank"] = worst
    for k in ks:
        for index, suffix in enumerate(
            ["weight_share", "necessary_share", "possible_share"]
        ):
            summary[f"top{k}_{suffix}"] = shares[k][:, index]
    endpoint = np.column_stack([a + low * slope, a + high * slope])
    summary["worst_regret"] = (endpoint.max(axis=0) - endpoint).max(axis=1)
    summary["minimax_regret_choice"] = np.isclose(
        summary.worst_regret, summary.worst_regret.min(), rtol=0, atol=2e-14
    )
    dominates = (values[None, :, :] >= values[:, None, :]).all(axis=2) & (
        values[None, :, :] > values[:, None, :]
    ).any(axis=2)
    summary["dominated_by_count"] = dominates.sum(axis=1)
    summary["pareto_efficient"] = summary.dominated_by_count.eq(0)
    summary["weight_low"], summary["weight_high"] = low, high
    summary["scope"] = (
        "fixed_candidates_uniform_preference_measure_not_outcome_probability"
    )
    return {
        "robust_candidates": summary,
        "weight_intervals": pd.DataFrame(segments),
        "weight_boundaries": pd.DataFrame(boundary_rows),
    }


def specification_audit(features, alpha=0.5, population_weight=0.7):
    """Compare prespecified transforms/internal weights, without outcome fitting."""
    columns = ["population", "poi_count", "vehicle_flow"]
    raw = features[columns].astype(float)
    if not np.isfinite(raw.to_numpy()).all() or (raw < 0).any().any():
        raise ValueError("Finite nonnegative features required for specification audit")
    if not 0 <= alpha <= 1 or not 0 <= population_weight <= 1:
        raise ValueError("Weights must be [0,1]")
    transforms = {}
    for method in ["minmax", "log1p_minmax", "percentile"]:
        x = np.log1p(raw) if method == "log1p_minmax" else raw.copy()
        z = pd.DataFrame(index=x.index)
        for c in columns:
            if x[c].nunique() == 1:
                z[c] = 0.0
            elif method == "percentile":
                ranks = x[c].rank(method="average")
                z[c] = (ranks - ranks.min()) / (ranks.max() - ranks.min())
            else:
                z[c] = (x[c] - x[c].min()) / (x[c].max() - x[c].min())
        transforms[method] = z

    def scored(z, beta):
        return pd.DataFrame(
            {
                "grid_id": features.grid_id,
                "integrated_score": alpha * z.vehicle_flow
                + (1 - alpha) * (beta * z.population + (1 - beta) * z.poi_count),
            }
        )

    base = scored(transforms["minmax"], population_weight)
    comparisons, ranks = [], []
    for method, z in transforms.items():
        for beta in sorted({0.0, 0.3, 0.5, 0.7, 1.0, float(population_weight)}):
            score = scored(z, beta)
            for k in [5, 10]:
                comparisons.append(
                    {
                        "normalization": method,
                        "population_weight_within_spatial": beta,
                        "mobility_weight": alpha,
                        **rank_metrics(base, score, k=k),
                    }
                )
            score["rank"] = score.integrated_score.rank(
                ascending=False, method="average"
            )
            score["normalization"] = method
            score["population_weight_within_spatial"] = beta
            ranks.append(score)
    diagnostics = []
    for c in columns:
        diagnostics.append(
            {
                "feature": c,
                "minimum": raw[c].min(),
                "maximum": raw[c].max(),
                "unique_values": raw[c].nunique(),
                "constant_feature": raw[c].nunique() == 1,
            }
        )
    return {
        "specification_comparison": pd.DataFrame(comparisons),
        "specification_ranks": pd.concat(ranks, ignore_index=True),
        "feature_diagnostics": pd.DataFrame(diagnostics),
    }
