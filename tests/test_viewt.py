"""Contract failures and behavioral tests for aggregate-flow decisions."""

import copy
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from transit_ooh.viewt import (
    analyze_bundle,
    daily_features,
    demo_bundle,
    milk_run,
    read_bundle,
    score_aggregate,
    validate_bundle,
    workbook,
)


@pytest.fixture
def bundle():
    return demo_bundle(days=5)


def test_excel_and_csv_roundtrip_preserve_source_and_keys(bundle, tmp_path):
    restored = read_bundle(workbook(bundle))
    assert restored.observation_type == "synthetic"
    assert restored.tables["candidates"].district_code.eq("11440").all()
    import json

    (tmp_path / "metadata.json").write_text(json.dumps(bundle.metadata))
    for name, frame in bundle.tables.items():
        frame.to_csv(tmp_path / (name + ".csv"), index=False)
    csv = read_bundle(tmp_path)
    pd.testing.assert_frame_equal(daily_features(restored), daily_features(csv))


@pytest.mark.parametrize(
    "field,value",
    [
        ("year", 2024),
        ("timezone", "UTC"),
        ("spatial_support_id", "OTHER"),
        ("spatial_unit", "dong"),
        ("start_date", "2025-09-01"),
        ("unit", "unique_people"),
    ],
)
def test_incompatible_sources_rejected(bundle, field, value):
    bundle.metadata["components"]["population_segments"][field] = value
    with pytest.raises(ValueError):
        validate_bundle(bundle)


def test_synthetic_real_mix_and_relabelling_rejected(bundle):
    bundle.metadata["components"]["poi"]["observation_type"] = "public_observed"
    with pytest.raises(ValueError, match="row observation_type"):
        validate_bundle(bundle)
    bundle.tables["poi"]["observation_type"] = "public_observed"
    with pytest.raises(ValueError, match="mix"):
        validate_bundle(bundle)


def test_missingness_duplicate_keys_and_poi_dates_rejected(bundle):
    broken = copy.deepcopy(bundle)
    broken.tables["population_segments"] = broken.tables["population_segments"].iloc[1:]
    with pytest.raises(ValueError, match="coverage"):
        validate_bundle(broken)
    broken = copy.deepcopy(bundle)
    broken.tables["vehicle_paths"] = pd.concat(
        [broken.tables["vehicle_paths"], broken.tables["vehicle_paths"].head(1)]
    )
    with pytest.raises(ValueError, match="duplicate"):
        validate_bundle(broken)
    bundle.metadata["components"]["poi"]["valid_to"] = "2020-01-01"
    with pytest.raises(ValueError, match="validity"):
        validate_bundle(bundle)


def test_population_tools_are_alternatives_not_sum(bundle):
    segments = daily_features(bundle)
    bundle.metadata["population_basis"] = "od_destination"
    od = daily_features(validate_bundle(bundle))
    pd.testing.assert_frame_equal(segments, od)
    bundle.tables["population_segments"]["population_flow"] *= 100
    pd.testing.assert_frame_equal(od, daily_features(bundle))


def test_vehicle_count_not_multiplied_by_path_rows_or_return_visit(bundle):
    daily = daily_features(bundle)
    paths = bundle.tables["vehicle_paths"]
    zone = bundle.tables["candidates"].zone_id.iloc[0]
    expected = (
        paths[(paths.zone_id == zone) & (paths.date == "2025-10-01")]
        .drop_duplicates(["route_id", "date", "hour"])
        .vehicle_flow.sum()
    )
    assert (
        daily[(daily.zone_id == zone) & (daily.date == "2025-10-01")].vehicle_flow.iloc[
            0
        ]
        == expected
    )


def test_weights_update_ranks_and_bootstrap_resamples_paired_days(bundle):
    r = analyze_bundle(bundle, 0.5, bootstrap_n=20)
    f = r["scores"]
    np.testing.assert_allclose(
        f.integrated_score, 0.5 * f.static_score + 0.5 * f.mobility_score
    )
    for alpha, component in [(0, "static"), (1, "mobility")]:
        s, _ = score_aggregate(f, alpha)
        np.testing.assert_allclose(s.integrated_score, s[component + "_score"])
        np.testing.assert_allclose(s.integrated_rank, s[component + "_rank"])
    base = r["weight_sensitivity"].query("mobility_weight == 0.5")
    assert base.top_k_overlap.eq(1).all()
    assert r["weight_ranks"].groupby("grid_id").integrated_rank.nunique().max() > 1
    reps = r["bootstrap_replicates"]
    assert reps.unique_days.lt(5).any()
    assert reps.drawn_days.nunique() > 1
    summary = r["selection_stability"]
    assert summary.top5_probability.sum() == pytest.approx(5)
    assert summary.top10_probability.sum() == pytest.approx(10)
    assert (summary.score_p975 >= summary.score_p025).all()
    assert r["temporal_holdout"].normalization.eq("train_only_frozen").all()


def test_hour_filter_and_insufficient_days_do_not_reuse_results(bundle):
    all_days = daily_features(bundle)
    morning = daily_features(bundle, hours=[8])
    assert morning.population.sum() < all_days.population.sum()
    r = analyze_bundle(bundle, dates=["2025-10-01"], bootstrap_n=20)
    assert r["selection_stability"].empty and r["temporal_holdout"].empty


def test_route_respects_direction_and_declares_assumptions(bundle):
    hubs = bundle.tables["candidates"].zone_id.iloc[[0, 4, 8]].tolist()
    route = milk_run(bundle, hubs, cycles=3)
    assert route.cycle.nunique() == 3 and route.observation_type.eq("synthetic").all()
    assert route.assumed_dwell_seconds.sum() == 3 * 3 * 5 * 60
    for _, g in route.groupby("cycle"):
        assert g.from_zone.iloc[0] == g.to_zone.iloc[-1] == hubs[0]
    broken = copy.deepcopy(bundle)
    broken.tables["vehicle_paths"] = broken.tables["vehicle_paths"].query(
        "sequence == 0"
    )
    with pytest.raises(ValueError, match="Disconnected"):
        milk_run(broken, hubs)


def test_viewt_ui_changes_weights_district_hours_and_upload_state():
    at = AppTest.from_file(
        Path(__file__).resolve().parents[1] / "app/streamlit_app.py", default_timeout=60
    ).run()
    assert not at.exception
    assert "SYNTHETIC" in at.warning[0].value
    assert at.selectbox(key="viewt_district").value == "마포구"
    assert at.slider(key="viewt_weight").value == 50
    at.slider(key="viewt_weight").set_value(0).run()
    assert not at.exception
    frames = [
        d.value
        for d in at.dataframe
        if "integrated_score" in d.value.columns and "static_score" in d.value.columns
    ]
    assert frames
    np.testing.assert_allclose(frames[0].integrated_score, frames[0].static_score)
    at.selectbox(key="viewt_district").set_value("강남구").run()
    assert not at.exception
    frames = [
        d.value
        for d in at.dataframe
        if "grid_id" in d.value.columns and "static_score" in d.value.columns
    ]
    assert frames[0].grid_id.str.contains("11680").all()
    at.multiselect(key="viewt_hours").set_value([8]).run()
    assert not at.exception
    at.radio(key="viewt_source").set_value("Excel·CSV 업로드").run()
    assert not at.exception
    assert any("업로드 대기" in w.value for w in at.warning)
    assert len(at.metric) == 0
