import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from transit_ooh.experiments import (
    ablation,
    cluster_bootstrap,
    holdout,
    weight_sensitivity,
)
from transit_ooh.io import load_config, sha256
from transit_ooh.pipeline import analyze
from transit_ooh.synthetic import generate


@pytest.fixture(scope="module")
def a():
    gps, _, ctx, meta, _ = generate(vehicles=4, days=4)
    return analyze(gps, load_config(), ctx, meta)


def test_bootstrap_cluster_selection_probabilities(a):
    reps, summary = cluster_bootstrap(a, n=10, k=5)
    assert len(reps) == 10 and summary.selection_probability.between(0, 1).all()
    assert summary.selection_probability.sum() == pytest.approx(5)
    assert (summary.score_p975 >= summary.score_p025).all()


def test_holdout_has_honest_unrun_season(a):
    h = holdout(a)
    assert len(h) == 5
    assert h[h.split == "season"].status.iloc[0] == "unrun_no_multiseason_observations"
    assert len(h[h.status == "executed"]) == 4
    assert "WITHIN" in h[h.split == "spatial_east_heldout"].metric_scope.iloc[0]


def test_weight_baseline_and_ablation(a):
    w, _ = weight_sensitivity(a)
    row = w[(w.mobility_weight - a.mobility_weight).abs() < 1e-8].iloc[0]
    assert row.top_k_overlap == 1 and row.spearman == pytest.approx(1)
    assert len(ablation(a)) == 4


def test_configured_alpha_and_fixed_legacy_baseline():
    from transit_ooh.scoring import score

    gps, _, ctx, meta, _ = generate(vehicles=1, days=2)
    cfg = load_config()
    cfg["mobility_weight"] = 0.2
    a = analyze(gps, cfg, ctx, meta)
    reps, summary = cluster_bootstrap(a, n=1, k=5)
    # A bootstrap with one cluster must reproduce the configured model exactly.
    assert reps.spearman.iloc[0] == pytest.approx(1.0)
    aligned = summary.set_index("grid_id").join(
        a.scores.set_index("grid_id").integrated_score
    )
    assert (aligned.score_p025 - aligned.integrated_score).abs().max() < 1e-12
    low, _ = score(a.features, 0.2)
    high, _ = score(a.features, 0.9)
    pd.testing.assert_series_equal(
        low.legacy_integrated_score, high.legacy_integrated_score
    )


def test_cli_rejects_event_as_gps(tmp_path):
    gps, *_ = generate(vehicles=1, days=1)
    gps["observation_unit"] = "obfuscated_route_stop"
    p = tmp_path / "events.csv"
    gps.to_csv(p, index=False)
    r = subprocess.run(
        [
            sys.executable,
            "-m",
            "transit_ooh.cli",
            "validate",
            "--gps",
            str(p),
            "--output",
            str(tmp_path / "out"),
        ],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 1 and "not continuous vehicle GPS" in r.stderr


def test_streamlit_controls_and_public_separation():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(
        Path(__file__).resolve().parents[1] / "app/streamlit_app.py", default_timeout=45
    ).run()
    assert not at.exception
    at.radio(key="app_mode").set_value("합성 GT 연구 데모").run()
    assert not at.exception
    initial_candidates = int(at.metric[0].value)
    assert initial_candidates > 0
    assert "SYNTHETIC" in at.warning[0].value
    # Grid, stop threshold and weights change the executed UI, not only labels.
    at.selectbox[0].set_value(400).run()
    assert not at.exception
    assert 0 < int(at.metric[0].value) < initial_candidates
    at.slider[1].set_value(0.0).run()
    assert not at.exception
    frames = [
        d.value
        for d in at.dataframe
        if isinstance(d.value, pd.DataFrame) and "integrated_score" in d.value
    ]
    assert frames
    assert (frames[-1].integrated_score - frames[-1].static_score).abs().max() < 1e-10
    at.radio(key="app_mode").set_value("실제 공개 자료 · 별도 분석").run()
    assert not at.exception
    assert "public_observed" in at.info[0].value
    assert len(at.tabs) == 0


def test_current_research_artifacts_match_manifest():
    latest = Path("reports/runs/latest.json")
    if not latest.exists():
        pytest.skip("Full research evidence not generated in this checkout")
    manifest = json.loads(Path(json.loads(latest.read_text())["manifest"]).read_text())
    assert (
        manifest["sample"]["gps_rows"] > 0
        and manifest["executed_experiments"]["robustness"] > 0
    )
    for path, expected in manifest["artifacts"].items():
        assert Path(path).exists(), path
        assert sha256(path) == expected, path


def test_missing_public_inputs_do_not_reuse_past_results(tmp_path):
    from transit_ooh.public_analysis import PUBLIC_OUTPUTS, analyze_public

    out = tmp_path / "reports"
    (out / "tables").mkdir(parents=True)
    (out / "figures").mkdir()
    for names in PUBLIC_OUTPUTS.values():
        for name in names:
            (out / "tables" / f"{name}.csv").write_text("stale_public_result")
    stale_figure = out / "figures/public_lade_event_stability.png"
    stale_figure.write_bytes(b"stale")
    user_file = out / "tables/user_notes.csv"
    user_file.write_text("keep me")
    result = analyze_public(root=tmp_path / "data/raw", output=out)
    assert all(s["status"] == "not_acquired" for s in result.values())
    assert not list((out / "tables").glob("public_*.csv"))
    assert not stale_figure.exists()
    assert user_file.read_text() == "keep me"
