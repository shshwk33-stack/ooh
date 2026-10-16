"""Synthetic instrument tests only; no real observations are generated."""

import copy
import json
from datetime import UTC, datetime
from io import BytesIO
from zipfile import ZipFile

import numpy as np
import pandas as pd
import pytest

import transit_ooh.field_validation as field


class Clock(datetime):
    current = datetime(2027, 1, 1, tzinfo=UTC)

    @classmethod
    def now(cls, tz=None):
        return cls.current


@pytest.fixture
def campaign(monkeypatch):
    monkeypatch.setattr(field, "datetime", Clock)
    Clock.current = datetime(2027, 1, 1, tzinfo=UTC)
    ids = [f"TEST-{i:02}" for i in range(12)]
    scores = pd.DataFrame(
        {
            "grid_id": ids,
            "static_score": np.linspace(1, 0, 12),
            "mobility_score": np.linspace(0, 1, 12),
            "longitude": [126.91] * 12,
            "latitude": [37.55] * 12,
        }
    )
    metadata = {
        "spatial_support_id": "TEST_ONLY",
        "training_end_date": "2026-12-31",
        "prediction_source": "Synthetic fixture for tests; NOT a real study",
        "prediction_observation_type": "estimated",
        "input_sha256": "0" * 64,
        "target": "manual_vehicle_passages",
        "site_mapping_review": "test fixture",
        "independence_plan": "test fixture",
    }
    dates = [f"2027-01-{d:02}" for d in range(3, 8)]
    data = field.freeze_campaign(scores, metadata, dates, alpha=0.8)
    _, _, schedule = field.read_campaign(data)
    obs = schedule.assign(count=np.tile(np.arange(12), 5), observer_id="test-observer")
    return data, obs, scores, metadata, dates


def test_freeze_blinds_collectors_and_rejects_early_or_synthetic_evaluation(campaign):
    data, obs, scores, meta, dates = campaign
    with ZipFile(BytesIO(data)) as z:
        assert b"score" not in z.read("observations_BLIND.csv")
        assert b"integrated_score" in z.read("predictions.csv")
    with pytest.raises(ValueError, match="uncompleted"):
        field.evaluate_campaign(data, obs, replicates=100)
    changed = copy.deepcopy(meta)
    changed["prediction_observation_type"] = "synthetic"
    with pytest.raises(ValueError, match="Synthetic"):
        field.freeze_campaign(scores, changed, dates)
    changed = copy.deepcopy(meta)
    changed["training_end_date"] = dates[0]
    with pytest.raises(ValueError, match="after all"):
        field.freeze_campaign(scores, changed, dates)


def test_frozen_predictions_and_schedule_hashes_detect_edits(campaign):
    data, *_ = campaign
    b = BytesIO()
    with ZipFile(BytesIO(data)) as src, ZipFile(b, "w") as dst:
        for name in src.namelist():
            raw = src.read(name)
            if name == "predictions.csv":
                raw += b"\n"
            dst.writestr(name, raw)
    with pytest.raises(ValueError, match="checksum"):
        field.read_campaign(b.getvalue())


def test_known_ranks_paired_delta_and_crossed_draws(campaign):
    data, obs, *_ = campaign
    Clock.current = datetime(2027, 1, 9, tzinfo=UTC)
    result = field.evaluate_campaign(data, obs, replicates=100)
    rho = result["model_metrics"].groupby("model").spearman.first()
    assert rho.to_dict() == pytest.approx({"A": -1, "B": 1, "C": 1})
    differences = result["paired_differences"].query("comparison == 'C_minus_A'")
    np.testing.assert_allclose(differences.estimate, 2)
    np.testing.assert_allclose(differences.p025, 2)
    assert len(result["bootstrap_draws"]) == 100
    assert (
        result["bootstrap_draws"]
        .day_indices.str.split(";")
        .map(lambda x: len(set(x)) < 5)
        .any()
    )
    assert (
        result["bootstrap_draws"]
        .site_indices.str.split(";")
        .map(lambda x: len(set(x)) < 12)
        .any()
    )
    assert result["audit"]["source_authentication"] == "not_independently_verified"


@pytest.mark.parametrize(
    "change",
    ["missing", "duplicate", "time", "duration", "fraction", "negative", "observer"],
)
def test_invalid_observations_do_not_become_results(campaign, change):
    data, obs, *_ = campaign
    Clock.current = datetime(2027, 1, 9, tzinfo=UTC)
    if change == "missing":
        obs = obs.iloc[1:]
    elif change == "duplicate":
        obs = pd.concat([obs, obs.head(1)])
    else:
        col, value = {
            "time": ("start_time", "13:00"),
            "duration": ("duration_minutes", 0),
            "fraction": ("count", 0.5),
            "negative": ("count", -1),
            "observer": ("observer_id", ""),
        }[change]
        obs = obs.astype({col: object})
        obs.loc[0, col] = value
    with pytest.raises(ValueError):
        field.evaluate_campaign(data, obs, replicates=100)


def test_constant_outcomes_report_undefined_not_perfect(campaign):
    data, obs, *_ = campaign
    Clock.current = datetime(2027, 1, 9, tzinfo=UTC)
    result = field.evaluate_campaign(data, obs.assign(count=0), replicates=100)
    assert result["model_metrics"].spearman.isna().all()
    assert result["model_metrics"].capture_share.isna().all()
    assert result["paired_differences"].valid_replicates.eq(0).all()
    assert result["paired_differences"].p025.isna().all()
    json.dumps(result["audit"], allow_nan=False)
