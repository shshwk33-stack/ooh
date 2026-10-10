"""Adversarial scientific contracts, derived from independently reviewed failure modes."""

import copy

import numpy as np
import pandas as pd
import pytest

from transit_ooh import experiments
from transit_ooh.features import extract_features
from transit_ooh.grids import Grid
from transit_ooh.io import load_config, provenance
from transit_ooh.pipeline import analyze
from transit_ooh.quality import normalize_gps
from transit_ooh.scoring import score, top_keys
from transit_ooh.spatial import spatial_features
from transit_ooh.stops import detect_stops, evaluate_stops
from transit_ooh.synthetic import generate


def stationary(n=21, frequency="30s", start="2026-01-01T00:00:00Z"):
    return provenance(
        pd.DataFrame(
            {
                "vehicle_id": "A",
                "timestamp": pd.date_range(start, periods=n, freq=frequency),
                "latitude": 37.5665,
                "longitude": 126.978,
            }
        ),
        "controlled_test",
        "synthetic",
        "vehicle_gps",
    )


@pytest.mark.parametrize("unit", ["s", "ms", "us", "ns"])
def test_external_parquet_timestamp_units(unit, tmp_path):
    d = stationary()
    d["timestamp"] = d.timestamp.dt.as_unit(unit)
    p = tmp_path / f"{unit}.parquet"
    d.to_parquet(p, index=False)
    q, _ = normalize_gps(pd.read_parquet(p))
    stops = detect_stops(Grid().project(q))
    assert len(stops) == 1
    assert stops.dwell_seconds.iloc[0] == 600


def test_isolated_spike_does_not_duplicate_visit():
    original = stationary()
    spike = original.copy()
    spike.loc[10, "longitude"] += 0.06
    q, audit = normalize_gps(spike)
    assert len(q) == len(original) - 1
    assert original.timestamp.iloc[11] in set(q.timestamp)
    assert q.point_valid.all()
    s = detect_stops(Grid().project(q))
    assert len(s) == 1 and s.dwell_seconds.iloc[0] == 600
    assert audit.set_index("issue").loc["isolated_spike_points_removed", "count"] == 1


def test_sparse_policy_is_explicit_and_never_bridges_overnight():
    d = stationary(5, "300s")
    fixed, _ = normalize_gps(d, gap_policy="fixed")
    adaptive, _ = normalize_gps(d, gap_policy="adaptive")
    assert fixed.interval_valid.sum() == 0
    assert adaptive.interval_valid.sum() == 4
    assert detect_stops(Grid().project(adaptive)).dwell_seconds.iloc[0] == 1200
    tail = d.copy()
    tail.timestamp += pd.Timedelta(days=1)
    q, _ = normalize_gps(pd.concat([d, tail]), gap_policy="adaptive")
    s = detect_stops(Grid().project(q))
    assert len(s) == 2 and s.dwell_seconds.sum() == 2400


def test_local_half_hour_boundary_and_visit_not_duplicated():
    d = stationary(5, "60s", "2026-01-01T03:28:00Z")  # Kolkata 08:58–09:02
    q, _ = normalize_gps(d)
    q = Grid().project(q)
    s = detect_stops(q)
    f, detail = extract_features(q, s, Grid(), timezone="Asia/Kolkata")
    hours = detail.groupby("hour").stop_seconds.sum().to_dict()
    assert hours == {8: 120.0, 9: 120.0}
    assert f.visit_frequency.sum() == 1 and detail.visit_frequency.sum() == 1


def test_uncovered_cell_keeps_missing_and_naive_validity_rejected():
    gps, _, c, m, _ = generate(vehicles=1, days=1)
    a = analyze(gps, load_config(), c, m)
    m = copy.deepcopy(m)
    m["complete_coverage"] = False
    joined = spatial_features(c, m, a.grid, a.scores.grid_id, a.gps)
    assert joined.population.isna().all() and joined.poi_count.isna().all()
    m["valid_from"] = "2026-09-21"
    with pytest.raises(ValueError, match="timezone"):
        spatial_features(c, m, a.grid, a.scores.grid_id, a.gps)


def test_matching_iou_threshold_is_exact_not_tunable_after_result():
    gt = pd.DataFrame(
        {
            "vehicle_id": ["A"],
            "start_time": [pd.Timestamp("2026-01-01T00:00Z")],
            "end_time": [pd.Timestamp("2026-01-01T00:10Z")],
            "dwell_seconds": [600],
        }
    )
    pred = gt.copy()
    pred["end_time"] = pred.start_time + pd.Timedelta(seconds=299)
    pred["dwell_seconds"] = 299
    assert evaluate_stops(pred, gt)[0]["tp"] == 0
    pred["end_time"] = pred.start_time + pd.Timedelta(seconds=300)
    pred["dwell_seconds"] = 300
    assert evaluate_stops(pred, gt)[0]["tp"] == 1


@pytest.fixture(scope="module")
def varied_analysis():
    gps, _, c, m, _ = generate(vehicles=4, days=4)
    return analyze(gps, load_config(), c, m)


def test_static_weight_direction_and_rank(varied_analysis):
    a = varied_analysis
    z = a.normalizer.transform(a.features)
    s, _ = score(a.features)
    np.testing.assert_allclose(s.static_score, 0.7 * z.population + 0.3 * z.poi_count)
    top = next(iter(top_keys(s, k=1)))
    assert s.set_index("grid_id").loc[top, "integrated_rank"] == s.integrated_rank.min()


def test_holdout_reuses_frozen_training_normalizer(varied_analysis, monkeypatch):
    original = experiments.score
    calls = []

    def audited(frame, *args, **kwargs):
        supplied = kwargs.get("normalizer")
        before = copy.deepcopy(supplied.bounds) if supplied else None
        result = original(frame, *args, **kwargs)
        calls.append((supplied, result[1], before, copy.deepcopy(result[1].bounds)))
        return result

    monkeypatch.setattr(experiments, "score", audited)
    experiments.holdout(varied_analysis)
    assert len(calls) == 8
    for first, second in zip(calls[::2], calls[1::2], strict=False):
        assert first[0] is None
        assert second[0] is first[1]
        assert second[2] == first[3] == second[3]


def test_cluster_resampling_really_replaces_and_changes_selection(varied_analysis):
    reps, summary = experiments.cluster_bootstrap(varied_analysis, n=20, seed=42)
    assert (reps.unique_drawn_clusters < reps.cluster_count).any()
    assert reps.drawn_clusters.nunique() > 1
    assert reps.spearman.min() < 0.999
    assert (
        (summary.selection_probability > 0) & (summary.selection_probability < 1)
    ).any()


def test_placebo_really_moves_joint_mobility_vectors(varied_analysis):
    r = experiments.permutation_placebo(varied_analysis, n=12)
    assert (r.changed_mobility_rows > 0).all()
    assert r.mobility_spearman.max() < 0.9
    assert r.spearman.nunique() > 1


def test_anchor_and_robust_detectors_compared_on_same_noisy_gps():
    gps, gt, c, m, _ = generate(vehicles=2, days=2, noise_m=15, seed=11)
    fixed = analyze(gps, {**load_config(), "stop_detector": "anchor"}, c, m)
    robust = analyze(gps, {**load_config(), "stop_detector": "robust"}, c, m)
    f1_old = evaluate_stops(fixed.stops, gt)[0]["f1"]
    f1_new = evaluate_stops(robust.stops, gt)[0]["f1"]
    assert f1_new > f1_old + 0.3
    expected = robust.gps.loc[robust.gps.interval_valid, "dt_seconds"].sum()
    assert (
        robust.detail.moving_seconds.sum() + robust.detail.stop_seconds.sum()
        == pytest.approx(expected)
    )


def test_robustness_uses_distinct_noiseless_reference():
    result = experiments.robustness(load_config(), quick=True)
    altered = result[(result.noise_m >= 15) & (result.scenario == "sampling_noise")]
    assert altered.mobility_spearman.lt(0.99).any()
    assert altered.top_k_overlap.lt(1).any()
