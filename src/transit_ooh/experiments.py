"""Declared sensitivity and selection-stability analyses without fake labels."""

from __future__ import annotations

import itertools

import numpy as np
import pandas as pd

from .features import aggregate
from .grids import Grid
from .pipeline import analyze
from .scoring import LEGACY_FEATURES, NEW_FEATURES, rank_metrics, score, top_keys
from .stops import evaluate_stops
from .synthetic import generate


def compare_models(analysis, k=5):
    s = analysis.scores
    rows = []
    for a, b in itertools.combinations(["static", "mobility", "integrated"], 2):
        rows.append(
            {
                "model_a": a,
                "model_b": b,
                **rank_metrics(s, s, a + "_score", b + "_score", k),
            }
        )
    rows.append(
        {
            "model_a": "legacy_integrated",
            "model_b": "integrated",
            **rank_metrics(s, s, "legacy_integrated_score", "integrated_score", k),
        }
    )
    return pd.DataFrame(rows)


def weight_sensitivity(analysis, k=5):
    rows = []
    ranks = []
    for alpha in np.linspace(0, 1, 11):
        s, _ = score(analysis.features, float(alpha), analysis.normalizer)
        rows.append(
            {
                "mobility_weight": float(alpha),
                "is_reference": bool(np.isclose(alpha, analysis.mobility_weight)),
                **rank_metrics(analysis.scores, s, k=k),
                "selected": ";".join(sorted(top_keys(s, k=k))),
            }
        )
        for r in s.itertuples():
            ranks.append(
                {
                    "mobility_weight": float(alpha),
                    "grid_id": r.grid_id,
                    "rank": r.integrated_rank,
                    "score": r.integrated_score,
                }
            )
    return pd.DataFrame(rows), pd.DataFrame(ranks)


def ablation(analysis, k=5):
    rows = []
    for omit in NEW_FEATURES:
        s, _ = score(
            analysis.features,
            alpha=analysis.mobility_weight,
            normalizer=analysis.normalizer,
            omit=omit,
        )
        rows.append(
            {
                "removed_feature": omit,
                "comparison": "new_model",
                **rank_metrics(analysis.scores, s, k=k),
            }
        )
    z = analysis.normalizer.transform(analysis.features)
    s = analysis.scores.copy()
    s["integrated_score"] = (
        0.6 * (0.5 * z.visit_frequency + 0.5 * z.total_dwell_minutes)
        + 0.4 * s.static_score
    )
    rows.append(
        {
            "removed_feature": "repeat_visits",
            "comparison": "legacy_repeat_ablation",
            **rank_metrics(
                analysis.scores, s, "legacy_integrated_score", "integrated_score", k
            ),
        }
    )
    return pd.DataFrame(rows)


def collinearity(analysis):
    f = analysis.features
    cols = list(
        dict.fromkeys(
            [*NEW_FEATURES, "repeat_visits", "unique_vehicles", "active_days"]
        )
    )
    rows = []
    for a, b in itertools.combinations(cols, 2):
        rows.append(
            {
                "feature_a": a,
                "feature_b": b,
                "spearman": f[a].corr(f[b], method="spearman")
                if f[a].nunique() > 1 and f[b].nunique() > 1
                else np.nan,
                "pearson": f[a].corr(f[b])
                if f[a].nunique() > 1 and f[b].nunique() > 1
                else np.nan,
            }
        )
    vifs = []
    for c in [*NEW_FEATURES, "repeat_visits"]:
        others = [v for v in [*NEW_FEATURES, "repeat_visits"] if v != c]
        x = np.column_stack([np.ones(len(f)), f[others].to_numpy()])
        y = f[c].to_numpy()
        pred = x @ np.linalg.lstsq(x, y, rcond=None)[0]
        sst = ((y - y.mean()) ** 2).sum()
        r2 = 1 - ((y - pred) ** 2).sum() / sst if sst > 0 else np.nan
        vifs.append(
            {
                "feature": c,
                "vif": 1 / (1 - r2) if r2 < 1 - 1e-12 else np.nan,
                "perfect_or_constant": bool(not np.isfinite(r2) or r2 >= 1 - 1e-12),
            }
        )
    return pd.DataFrame(rows), pd.DataFrame(vifs)


def permutation_placebo(analysis, n=100, seed=42, k=5):
    rng = np.random.default_rng(seed)
    rows = []
    cols = list(dict.fromkeys(NEW_FEATURES + LEGACY_FEATURES))
    for rep in range(n):
        f = analysis.features.copy()
        f[cols] = f[cols].to_numpy()[rng.permutation(len(f))]
        s, _ = score(f, alpha=analysis.mobility_weight, normalizer=analysis.normalizer)
        rows.append(
            {
                "replicate": rep,
                "design": "joint_mobility_row_permutation",
                "meaning": "decision_sensitivity_not_accuracy",
                "changed_mobility_rows": int(
                    (f[cols].to_numpy() != analysis.features[cols].to_numpy())
                    .any(axis=1)
                    .sum()
                ),
                **rank_metrics(analysis.scores, s, k=k),
                **{
                    f"mobility_{key}": val
                    for key, val in rank_metrics(
                        analysis.scores, s, "mobility_score", "mobility_score", k
                    ).items()
                },
                "overlap_with_static": rank_metrics(
                    s, s, "static_score", "integrated_score", k
                )["top_k_overlap"],
            }
        )
    return pd.DataFrame(rows)


def cluster_bootstrap(analysis, n=100, seed=42, k=5):
    rng = np.random.default_rng(seed)
    detail = analysis.detail
    vehicles = sorted(detail.vehicle_id.unique())
    rows = []
    selection = {k: 0 for k in analysis.scores.grid_id}
    all_scores = []
    spatial_cols = [
        c
        for c in ["grid_id", "population", "poi_count", "spatial_covered"]
        if c in analysis.features
    ]
    for rep in range(n):
        parts = []
        draws = rng.choice(vehicles, len(vehicles), replace=True)
        for j, v in enumerate(draws):
            d = detail[detail.vehicle_id == v].copy()
            d["vehicle_id"] = f"bootstrap-{j}"
            parts.append(d)
        f = aggregate(
            pd.concat(parts, ignore_index=True), analysis.scores.grid_id
        ).merge(analysis.features[spatial_cols], on="grid_id")
        s, _ = score(f, alpha=analysis.mobility_weight, normalizer=analysis.normalizer)
        all_scores.append(s.set_index("grid_id").integrated_score)
        for key in top_keys(s, k=k):
            selection[key] += 1
        rows.append(
            {
                "replicate": rep,
                "cluster_count": len(vehicles),
                "unique_drawn_clusters": len(set(draws)),
                "drawn_clusters": ";".join(draws),
                **rank_metrics(analysis.scores, s, k=k),
                **{
                    f"mobility_{key}": val
                    for key, val in rank_metrics(
                        analysis.scores, s, "mobility_score", "mobility_score", k
                    ).items()
                },
            }
        )
    arr = pd.DataFrame(all_scores)
    summary = []
    for key in selection:
        p = selection[key] / n
        summary.append(
            {
                "grid_id": key,
                "selection_probability": p,
                "mc_standard_error": float(np.sqrt(p * (1 - p) / n)),
                "score_p025": arr[key].quantile(0.025),
                "score_p975": arr[key].quantile(0.975),
                "replicates": n,
                "resampling_unit": "vehicle_all_days",
                "interval_scope": "conditional_stability_not_population_CI",
            }
        )
    return pd.DataFrame(rows), pd.DataFrame(summary)


def holdout(analysis, k=5):
    d = analysis.detail
    days = sorted(d.date.unique())
    vehicles = sorted(d.vehicle_id.unique())
    definitions = [
        ("temporal", d.date.isin(days[: len(days) // 2])),
        ("vehicle", d.vehicle_id.isin(vehicles[: len(vehicles) // 2])),
        ("time_of_day", d.hour < 12),
    ]
    spatial = analysis.features[
        [
            c
            for c in ["grid_id", "population", "poi_count", "spatial_covered"]
            if c in analysis.features
        ]
    ]
    rows = []
    for name, mask in definitions:
        train = d[mask]
        test = d[~mask]
        if train.empty or test.empty:
            rows.append({"split": name, "status": "not_applicable_empty_partition"})
            continue

        def prepare(part):
            f = aggregate(part, analysis.scores.grid_id)
            units = len(part[["vehicle_id", "date"]].drop_duplicates())
            for c in [
                "moving_seconds",
                "stop_seconds",
                "visit_frequency",
                "repeat_visits",
                "total_dwell_minutes",
            ]:
                f[c] /= max(units, 1)
            return f.merge(spatial, on="grid_id"), units

        a, na = prepare(train)
        b, nb = prepare(test)
        sa, norm = score(a, alpha=analysis.mobility_weight)
        sb, _ = score(b, alpha=analysis.mobility_weight, normalizer=norm)
        rows.append(
            {
                "split": name,
                "status": "executed",
                "training_vehicle_days": na,
                "heldout_vehicle_days": nb,
                "normalization": "fit_train_rates_per_vehicle_day",
                "metric_scope": "same_candidates_train_vs_holdout_decision_stability",
                **rank_metrics(sa, sb, k=k),
                **{
                    f"mobility_{key}": val
                    for key, val in rank_metrics(
                        sa, sb, "mobility_score", "mobility_score", k
                    ).items()
                },
            }
        )
    # Held-out region: train normalization on west, compare models ONLY within east.
    f = analysis.features.copy()
    xs = np.array([analysis.grid.center(key)[0] for key in f.grid_id])
    cut = np.median(xs)
    _, norm = score(f[xs < cut], alpha=analysis.mobility_weight)
    east, _ = score(f[xs >= cut], alpha=analysis.mobility_weight, normalizer=norm)
    rows.append(
        {
            "split": "spatial_east_heldout",
            "status": "executed",
            "normalization": "fit_west_apply_east",
            "metric_scope": "static_vs_integrated_WITHIN_heldout_region_not_transfer_accuracy",
            **rank_metrics(east, east, "static_score", "integrated_score", k),
        }
    )
    rows.append(
        {
            "split": "season",
            "status": "unrun_no_multiseason_observations",
            "metric_scope": "cannot_infer_seasonal_generalization",
        }
    )
    return pd.DataFrame(rows)


def robustness(config, quick=False):
    rows = []
    seeds = config["experiments"]["seeds"] if not quick else [42]
    variants = [
        {
            "name": "sampling_noise",
            "noise_m": noise,
            "sample_seconds": interval,
            "vehicles": 2,
            "days": 2,
        }
        for noise in [0, 5, 15, 35]
        for interval in [30, 120, 300]
    ]
    variants += [
        {
            "name": "vehicle_count",
            "vehicles": v,
            "days": 2,
            "noise_m": 5,
            "sample_seconds": 30,
        }
        for v in [1, 4, 8]
    ]
    variants += [
        {
            "name": "period_length",
            "vehicles": 2,
            "days": d,
            "noise_m": 5,
            "sample_seconds": 30,
        }
        for d in [1, 3, 6]
    ]
    variants += [
        {
            "name": "irregular_dropout",
            "vehicles": 2,
            "days": 2,
            "noise_m": 5,
            "sample_seconds": 30,
            "irregular": True,
            "dropout": 0.25,
        }
    ]
    for seed in seeds:
        baselines = {}
        for v in variants:
            args = {k: val for k, val in v.items() if k != "name"}
            gps, gt, ctx, meta, _ = generate(
                seed=seed, scenario="mixed_delivery", scenario_seed=seed, **args
            )
            a = analyze(gps, config, ctx, meta)
            metrics, _ = evaluate_stops(a.stops, gt)
            key = (args["vehicles"], args["days"])
            if key not in baselines:
                bg, _, bc, bm, _ = generate(
                    seed=seed,
                    scenario="mixed_delivery",
                    scenario_seed=seed,
                    vehicles=key[0],
                    days=key[1],
                    noise_m=0,
                    sample_seconds=30,
                )
                baselines[key] = analyze(bg, config, bc, bm)
            base = baselines[key]
            rows.append(
                {
                    "seed": seed,
                    "scenario": v["name"],
                    **args,
                    **metrics,
                    **rank_metrics(base.scores, a.scores, k=config["top_k"]),
                    **{
                        f"mobility_{key}": val
                        for key, val in rank_metrics(
                            base.scores,
                            a.scores,
                            "mobility_score",
                            "mobility_score",
                            config["top_k"],
                        ).items()
                    },
                    "rank_reference": "same_fleet_period_seed_noiseless_30s",
                    "valid_intervals": int(a.gps.interval_valid.sum()),
                    "gps_rows": len(gps),
                    "stop_radius_m": config["stop_radius_m"],
                    "max_gap_seconds": config["max_gap_seconds"],
                }
            )
    return pd.DataFrame(rows)


def grid_sensitivity(gps, context, meta, config, baseline):
    rows = []
    anchors = baseline.scores[["grid_id", "integrated_score"]].copy()
    xy = [baseline.grid.center(k) for k in anchors.grid_id]
    for size, offset in [(100, 0), (200, 0), (400, 0), (200, 50), (200, 100)]:
        grid = Grid(config["projected_crs"], size, offset, offset)
        a = analyze(gps, config, context, meta, grid=grid)
        mapped = anchors[["grid_id"]].copy()
        lookup = a.scores.set_index("grid_id").integrated_score
        mapped["integrated_score"] = [lookup.get(grid.key(x, y), np.nan) for x, y in xy]
        rows.append(
            {
                "grid_size_m": size,
                "origin_offset_m": offset,
                "native_candidates": len(a.scores),
                "comparison_support": "fixed_200m_anchor_centers; common covered anchors only",
                **rank_metrics(anchors, mapped, k=config["top_k"]),
            }
        )
    return pd.DataFrame(rows)


def detector_benchmark(config, quick=False):
    """Paired algorithm comparison on independently generated held-out schedules.

    Thresholds are held fixed. These are synthetic physical stops, including long
        signals, not delivery-purpose labels. Seeds generate routes as well as noise.
    """
    from .quality import normalize_gps
    from .stops import detect_stops

    rows = []
    seeds = config["experiments"].get("heldout_scenario_seeds", [101, 202, 303])
    if quick:
        seeds = seeds[:1]
    for scene_seed in seeds:
        for scenario in ["mixed_delivery", "slow_traffic", "warehouse"]:
            for noise, accuracy, correlated in [
                (5, "reported", False),
                (15, "reported", True),
                (35, "missing", True),
                (35, "overconfident", True),
            ]:
                gps, gt, _, _, _ = generate(
                    seed=scene_seed + 7000,
                    vehicles=2,
                    days=2,
                    scenario=scenario,
                    scenario_seed=scene_seed,
                    noise_m=noise,
                    accuracy_mode=accuracy,
                    correlated_noise=correlated,
                )
                clean, _ = normalize_gps(
                    gps, gap_policy=config.get("gap_policy", "fixed")
                )
                projected = Grid(
                    config["projected_crs"], config["grid_size_m"]
                ).project(clean)
                for method in ["anchor", "robust"]:
                    predicted = detect_stops(
                        projected,
                        method=method,
                        radius_m=config["stop_radius_m"],
                        min_seconds=config["min_stop_seconds"],
                        max_radius_m=config.get("max_stop_radius_m", 90),
                    )
                    metrics, _ = evaluate_stops(predicted, gt)
                    rows.append(
                        {
                            "scenario_seed": scene_seed,
                            "schedule": scenario,
                            "noise_m": noise,
                            "accuracy_mode": accuracy,
                            "correlated_noise": correlated,
                            "method": method,
                            "thresholds": "fixed_before_heldout_evaluation",
                            "truth_scope": "physical_stops_ge120s_including_long_signals",
                            **metrics,
                        }
                    )
    return pd.DataFrame(rows)
