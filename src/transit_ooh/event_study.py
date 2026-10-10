"""Real LaDe event-based selection stability, independent of the GPS demo.

An AOI is the provider's grouping key, NOT a matched OSM polygon. Counts measure
recorded tasks/fixes, not visits, dwell, vehicle exposure, or advertising impact.
"""

import numpy as np
import pandas as pd
from .scoring import rank_metrics, top_keys
from .io import save_table


def lade_event_study(events, output, replicates=200, seed=42):
    d = events.copy()
    d["site_key"] = (
        d.city.astype(str) + ":" + d.region_id.astype(str) + ":" + d.aoi_id.astype(str)
    )
    d["month"] = d.delivery_time.str.slice(0, 2).astype(int)
    counts = d.groupby("site_key").agg(
        task_count=("order_id", "nunique"),
        couriers=("courier_id", "nunique"),
        days=("ds", "nunique"),
    )
    # Reporting/selection population is explicitly conditional on this full observed panel.
    eligible = counts[(counts.task_count >= 10) & (counts.couriers >= 2)].index
    matrix = d.pivot_table(
        index="courier_id",
        columns="site_key",
        values="order_id",
        aggfunc="nunique",
        fill_value=0,
    ).reindex(columns=eligible, fill_value=0)
    base = pd.DataFrame(
        {"grid_id": eligible, "integrated_score": matrix.sum().to_numpy(dtype=float)}
    )
    k = min(10, len(base))
    rng = np.random.default_rng(seed)
    hits = np.zeros(len(base))
    boot = []
    for rep in range(replicates):
        sample = matrix.to_numpy()[rng.integers(0, len(matrix), len(matrix))].sum(
            axis=0
        )
        b = pd.DataFrame(
            {"grid_id": eligible, "integrated_score": sample.astype(float)}
        )
        chosen = top_keys(b, k=k)
        hits += np.array([x in chosen for x in eligible])
        boot.append(
            {
                "replicate": rep,
                **rank_metrics(base, b, k=k),
                "resampling_unit": "courier_all_available_days",
                "source": "LaDe-D Jilin",
                "population": "observed_AOIs_with_10_tasks_and_2_couriers",
            }
        )
    fix_counts = (
        d.drop_duplicates(
            [
                "courier_id",
                "delivery_gps_time",
                "delivery_gps_lat",
                "delivery_gps_lng",
                "site_key",
            ]
        )
        .groupby("site_key")
        .size()
        .reindex(eligible, fill_value=0)
    )
    result = counts.loc[eligible].reset_index()
    result["distinct_event_fixes"] = fix_counts.to_numpy()
    result["top10_selection_probability"] = hits / replicates
    result["bootstrap_replicates"] = replicates
    result["measure"] = "recorded_delivery_tasks_not_vehicle_visits"
    result["source"] = "LaDe-D Jilin"
    result["coordinate_join"] = "provider_city_region_aoi_key_only"
    save_table(
        result, output / "tables/public_lade_aoi_stability.csv", "public_observed"
    )
    save_table(
        pd.DataFrame(boot),
        output / "tables/public_lade_bootstrap.csv",
        "public_observed",
    )
    rows = []
    months = sorted(d.month.unique())
    for train_month, test_month in zip(months[:-1], months[1:]):
        a = (
            d[d.month == train_month]
            .groupby("site_key")
            .order_id.nunique()
            .reindex(eligible, fill_value=0)
        )
        b = (
            d[d.month == test_month]
            .groupby("site_key")
            .order_id.nunique()
            .reindex(eligible, fill_value=0)
        )
        sa = pd.DataFrame(
            {"grid_id": eligible, "integrated_score": a.to_numpy(dtype=float)}
        )
        sb = pd.DataFrame(
            {"grid_id": eligible, "integrated_score": b.to_numpy(dtype=float)}
        )
        rows.append(
            {
                "train_month": int(train_month),
                "heldout_month": int(test_month),
                **rank_metrics(sa, sb, k=k),
                "comparison": "adjacent_month_event_count_ranking_same_observed_AOI_panel",
                "claim": "descriptive_stability_not_predictive_accuracy",
                "source": "LaDe-D Jilin 2022",
            }
        )
    save_table(
        pd.DataFrame(rows),
        output / "tables/public_lade_monthly_stability.csv",
        "public_observed",
    )
    alt = pd.DataFrame(
        {"grid_id": eligible, "integrated_score": fix_counts.to_numpy(dtype=float)}
    )
    comparison = rank_metrics(base, alt, k=k)
    return {
        "eligible_AOIs": len(base),
        "eligibility": "at_least_10_tasks_and_2_couriers_in_full_observed_panel",
        "courier_clusters": len(matrix),
        "bootstrap_replicates": replicates,
        "stable_AOIs_selection_ge_0_8": int((hits / replicates >= 0.8).sum()),
        "task_vs_distinct_event_fix_ranking": comparison,
        "adjacent_month_comparisons": len(rows),
        "month_top10_overlap_range": [
            float(min(r["top_k_overlap"] for r in rows)),
            float(max(r["top_k_overlap"] for r in rows)),
        ]
        if rows
        else None,
        "limitations": "available-panel selection; missing operations unknown; events are not continuous GPS or vehicle visits; no external value labels",
    }
