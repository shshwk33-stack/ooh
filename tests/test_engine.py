import copy
import importlib.util
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from pyproj import Transformer
from transit_ooh.io import load_config, provenance, read_table
from transit_ooh.quality import normalize_gps
from transit_ooh.grids import Grid
from transit_ooh.stops import detect_stops, evaluate_stops
from transit_ooh.synthetic import generate
from transit_ooh.pipeline import analyze
from transit_ooh.scoring import score, rank_metrics, MinMax, top_keys
from transit_ooh.spatial import spatial_features
from transit_ooh.sources import amazon_stops, download, SourceError


@pytest.fixture(scope="module")
def sample():
    return generate(vehicles=2, days=2, seed=42)


@pytest.fixture(scope="module")
def analysis(sample):
    gps, _, ctx, meta, _ = sample
    return analyze(gps, load_config(), ctx, meta)


def small_gps(times, lat=None, lon=None):
    n = len(times)
    return provenance(
        pd.DataFrame(
            {
                "vehicle_id": ["A"] * n,
                "timestamp": times,
                "latitude": lat if lat is not None else [37.5665] * n,
                "longitude": lon if lon is not None else [126.978] * n,
            }
        ),
        "test_gt",
        "synthetic",
        "synthetic_vehicle_gps",
    )


def test_timezone_conversion():
    d, _ = normalize_gps(small_gps(["2026-09-21 09:00", "2026-09-21 09:01"]))
    assert str(d.timestamp.iloc[0]) == "2026-09-21 00:00:00+00:00"


def test_utc_preserved():
    d, _ = normalize_gps(small_gps(["2026-09-21T09:00:00Z"]))
    assert d.timestamp.iloc[0].hour == 9


def test_original_order_and_duplicates_audited():
    d, q = normalize_gps(
        small_gps(["2026-01-01 09:02", "2026-01-01 09:00", "2026-01-01 09:00"])
    )
    counts = q.set_index("issue")["count"]
    assert counts.negative_time_deltas_input_order == 1
    assert counts.duplicate_vehicle_timestamp == 1 and len(d) == 2


def test_invalid_coordinates_removed():
    d, q = normalize_gps(small_gps(["2026-01-01"] * 2, [95, 37.5], [127, 127]))
    assert len(d) == 1 and q.set_index("issue").loc["invalid_coordinates", "count"] == 1


def test_jumps_and_gaps_not_bridged():
    d, _ = normalize_gps(
        small_gps(
            [
                "2026-01-01 09:00",
                "2026-01-01 09:01",
                "2026-01-01 09:02",
                "2026-01-01 10:02",
            ],
            lon=[126.978, 128, 126.978, 126.978],
        )
    )
    assert not d.interval_valid.any()


def test_missing_provenance_rejected():
    with pytest.raises(ValueError, match="source"):
        normalize_gps(small_gps(["2026-01-01"]).drop(columns="source"))


def test_event_data_is_not_gps():
    d = small_gps(["2026-01-01"])
    d["observation_unit"] = "courier_delivery_event_nearest_gps"
    with pytest.raises(ValueError, match="not continuous"):
        normalize_gps(d)


def test_metric_crs_and_roundtrip():
    with pytest.raises(ValueError, match="metres"):
        Grid("EPSG:4326")
    g = Grid()
    d = g.project(small_gps(["2026-01-01"]))
    back = Transformer.from_crs(g.crs, 4326, always_xy=True)
    lon, lat = back.transform(d.x.iloc[0], d.y.iloc[0])
    assert lon == pytest.approx(126.978, abs=1e-8) and lat == pytest.approx(
        37.5665, abs=1e-8
    )
    with pytest.raises(ValueError, match="outside"):
        g.project(pd.DataFrame({"longitude": [-122.3], "latitude": [47.5]}))


def test_segment_time_conservation_and_boundary():
    g = Grid(size=100)
    parts = g.segment_parts(50, 50, 250, 50)
    assert parts == [("0:0", 0.25), ("1:0", 0.5), ("2:0", 0.25)]
    assert sum(f for _, f in g.segment_parts(50, 50, 350, 470)) == pytest.approx(1)


def test_stop_duration_uses_elapsed_time():
    d, _ = normalize_gps(
        small_gps(
            [
                "2026-01-01 09:00",
                "2026-01-01 09:00:40",
                "2026-01-01 09:02",
                "2026-01-01 09:03:30",
            ]
        )
    )
    s = detect_stops(Grid().project(d))
    assert len(s) == 1 and s.dwell_seconds.iloc[0] == 210


def test_gap_splits_stop():
    d, _ = normalize_gps(
        small_gps(
            [
                "2026-01-01 09:00",
                "2026-01-01 09:02",
                "2026-01-01 10:00",
                "2026-01-01 10:02",
            ]
        )
    )
    s = detect_stops(Grid().project(d))
    assert len(s) == 2 and s.dwell_seconds.sum() == 240


def test_one_to_one_episode_matching(analysis, sample):
    gt = sample[1]
    perfect = gt.copy()
    r, _ = evaluate_stops(perfect, gt)
    assert r["f1"] == 1 and r["matched_duration_mae_seconds"] == 0
    duplicated = pd.concat([perfect, perfect.iloc[:1]])
    r, _ = evaluate_stops(duplicated, gt)
    assert r["fp"] == 1 and r["recall"] == 1
    r, _ = evaluate_stops(analysis.stops, gt)
    assert r["f1"] > 0.9


def test_no_predictions_is_not_passing(sample):
    gt = sample[1]
    r, _ = evaluate_stops(gt.iloc[:0], gt)
    assert r["recall"] == 0 and r["matched_duration_mae_seconds"] is None


def test_sparse_sampling_no_valid_intervals_remains_numeric():
    gps, gt, ctx, meta, _ = generate(vehicles=1, days=1, sample_seconds=300)
    a = analyze(gps, load_config(), ctx, meta)
    assert len(a.stops) == 0 and a.gps.interval_valid.sum() == 0
    assert (a.scores.mobility_score == 0).all()
    assert rank_metrics(a.scores, a.scores)["spearman"] == pytest.approx(1.0)


def test_presence_conservation(analysis):
    expected = analysis.gps.loc[analysis.gps.interval_valid, "dt_seconds"].sum()
    assert analysis.detail[
        ["moving_seconds", "stop_seconds"]
    ].sum().sum() == pytest.approx(expected)
    assert analysis.features.stop_seconds.sum() == pytest.approx(
        analysis.stops.dwell_seconds.sum()
    )


def test_spatial_join_invariant_to_row_order(sample, analysis):
    gps, _, ctx, meta, _ = sample
    g = analysis.grid
    a = spatial_features(ctx, meta, g, analysis.scores.grid_id, analysis.gps)
    b = spatial_features(
        ctx.sample(frac=1, random_state=99),
        meta,
        g,
        analysis.scores.grid_id,
        analysis.gps,
    )
    pd.testing.assert_frame_equal(a, b)


@pytest.mark.parametrize(
    "key,value",
    [
        ("observation_type", "public_observed"),
        ("valid_to", "2020-01-01T00:00:00Z"),
        ("projected_crs", "EPSG:32651"),
    ],
)
def test_mismatched_context_rejected(sample, analysis, key, value):
    _, _, ctx, meta, _ = sample
    meta = copy.deepcopy(meta)
    meta[key] = value
    with pytest.raises(ValueError):
        spatial_features(
            ctx, meta, analysis.grid, analysis.scores.grid_id, analysis.gps
        )


def test_models_formula_and_contributions(analysis):
    s = analysis.scores
    np.testing.assert_allclose(
        s.integrated_score, 0.6 * s.mobility_score + 0.4 * s.static_score
    )
    np.testing.assert_allclose(
        s.integrated_score,
        s[
            [
                "moving_contribution",
                "stop_contribution",
                "visit_contribution",
                "spatial_contribution",
            ]
        ].sum(axis=1),
    )
    norm = analysis.normalizer.transform(analysis.features)
    np.testing.assert_allclose(
        s.legacy_mobility_score,
        0.4 * norm.visit_frequency
        + 0.4 * norm.total_dwell_minutes
        + 0.2 * norm.repeat_visits,
    )


def test_missing_spatial_not_imputed(analysis):
    f = analysis.features.drop(columns=["population", "poi_count"])
    s, _ = score(f)
    assert s.static_score.isna().all() and s.integrated_score.isna().all()
    assert s.mobility_score.notna().all()


def test_holdout_scaler_does_not_refit():
    n = MinMax().fit(pd.DataFrame({"x": [0, 10]}), ["x"])
    assert n.transform(pd.DataFrame({"x": [5, 100]})).x.tolist() == [0.5, 1.0]


def test_rank_metrics_ties_and_topk():
    a = pd.DataFrame({"grid_id": ["b", "a", "c"], "integrated_score": [1.0, 1.0, 0.0]})
    assert top_keys(a, k=1) == {"a"}
    m = rank_metrics(a, a, k=2)
    assert m["spearman"] == 1 and m["top_k_overlap"] == 1


@pytest.mark.parametrize("seed", [11, 42, 73])
def test_seed_reproducibility(seed):
    a = generate(seed=seed, vehicles=1, days=1)
    b = generate(seed=seed, vehicles=1, days=1)
    pd.testing.assert_frame_equal(a[0], b[0])
    pd.testing.assert_frame_equal(a[1], b[1])


def test_csv_parquet_roundtrip(tmp_path, sample):
    gps = sample[0]
    gps.to_csv(tmp_path / "x.csv", index=False)
    gps.to_parquet(tmp_path / "x.parquet", index=False)
    a, _ = normalize_gps(read_table(tmp_path / "x.csv"))
    b, _ = normalize_gps(read_table(tmp_path / "x.parquet"))
    np.testing.assert_allclose(a.latitude, b.latitude, atol=1e-10)
    assert a.timestamp.equals(b.timestamp)


def test_amazon_adapter_does_not_invent_time_or_vehicle():
    d = amazon_stops(
        {
            "route": {
                "station_code": "X",
                "date_YYYY_MM_DD": "2018-01-01",
                "departure_time_utc": "09:00:00",
                "stops": {"AA": {"lat": 47.0, "lng": -122.0, "type": "Dropoff"}},
            }
        }
    )
    assert "timestamp" not in d and "vehicle_id" not in d
    assert d.observation_unit.iloc[0] == "obfuscated_route_stop"


def test_external_failure_is_explicit(tmp_path):
    import requests

    class Broken:
        def get(self, *a, **kw):
            raise requests.ConnectionError("test failure")

    with pytest.raises(SourceError):
        download("https://example.org/data", tmp_path / "data.csv", session=Broken())
    assert not (tmp_path / "data.csv").exists()


def test_legacy_regression_facts():
    spec = importlib.util.spec_from_file_location(
        "legacy", Path("scripts/audit_legacy.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    result, _ = mod.run(42)
    assert (
        result["gps_rows"],
        result["occupied_grids"],
        result["candidate_grids"],
        result["stops"],
    ) == (65, 19, 6, 11)
    assert result["estimated_stop_minutes"] - result["generated_stop_minutes"] == 25


@pytest.mark.xfail(
    strict=True,
    reason="Preserved historical PoC counts GPS points × 5min: 190 ≠ 165; regression evidence, not a new-engine failure",
)
def test_original_poc_dwell_should_equal_schedule():
    spec = importlib.util.spec_from_file_location(
        "legacy", Path("scripts/audit_legacy.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    result, _ = mod.run(42)
    assert result["estimated_stop_minutes"] == result["generated_stop_minutes"]
