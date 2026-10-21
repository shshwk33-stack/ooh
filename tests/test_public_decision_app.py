"""Acquired report integrity and user controls without provider originals."""

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from transit_ooh.public_decision import compare_portfolios

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports/public_decision"


def _require_report():
    if not (REPORT / "summary.json").is_file():
        pytest.skip("Acquired public research report has not been generated")


def test_acquired_study_manifest_and_selection_reproduce_without_provider_originals():
    _require_report()
    manifest = json.loads((REPORT / "summary.json").read_text())
    for relative, expected in manifest["artifacts_sha256"].items():
        assert hashlib.sha256((REPORT / relative).read_bytes()).hexdigest() == expected
    features = pd.read_csv(
        REPORT / "tables/candidate_features.csv", dtype={"grid_id": str}
    )
    study = compare_portfolios(features)
    reported = pd.read_csv(REPORT / "tables/portfolio_comparison.csv")
    primary = reported[(reported.k == 5) & (reported.weight_low == 0)]
    np.testing.assert_allclose(primary.worst_regret, study["comparison"].worst_regret)
    assert study["solver"]["optimal_sets"] == manifest["optimal_sets"]


def test_public_dashboard_weight_extremes_custom_k_and_csv():
    _require_report()
    at = AppTest.from_file(ROOT / "app/streamlit_app.py", default_timeout=60).run()
    assert not at.exception
    assert at.radio(key="app_mode").value == "공개자료 · 강건한 후보 선정"
    chart = json.loads(at.get("deck_gl_json_chart")[0].proto.json)
    text = next(layer for layer in chart["layers"] if layer["@@type"] == "TextLayer")
    # Pydeck string literals otherwise become invalid field expressions and
    # silently hide Korean labels even though the point layer still renders.
    assert text["characterSet"] == "auto"
    assert text["getTextAnchor"] == "start"
    assert not text["fontFamily"].startswith("@@=")
    for weight, column in [(0, "static_score"), (100, "mobility_score")]:
        at.slider(key="public_alpha").set_value(weight).run()
        assert not at.exception
        current = next(d.value for d in at.dataframe if "현재 순위" in d.value)
        np.testing.assert_allclose(current.integrated_score, current[column])
    at.selectbox(key="public_k").set_value(3)
    at.slider(key="public_weight_range").set_value((30, 70)).run()
    assert not at.exception
    current = next(d.value for d in at.dataframe if "현재 순위" in d.value)
    assert current["강건 선택"].sum() == 3
    assert current["현재 Top-K"].sum() == 3
    assert any("CSV" in button.label for button in at.get("download_button"))
