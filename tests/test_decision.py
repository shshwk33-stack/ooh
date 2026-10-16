"""Analytical counterexamples, not research observations."""

import numpy as np
import pandas as pd
import pytest

from transit_ooh.decision import specification_audit, weight_audit
from transit_ooh.viewt import analyze_bundle, demo_bundle, score_aggregate


def test_continuous_analysis_finds_narrow_winner_missed_by_five_percent_grid():
    d = pd.DataFrame(
        {
            "grid_id": ["A", "B", "C"],
            "static_score": [1.0, 0.0, 0.481],
            "mobility_score": [0.0, 12 / 13, 0.481],
        }
    )
    # C only wins around alpha=.52; neither .50 nor .55 identifies this.
    # Solve crossings explicitly: A=C -> .519; C=B -> .481*13/12.
    r = weight_audit(d, ks=(1, 2))
    c = r["robust_candidates"].set_index("grid_id").loc["C"]
    assert c.top1_weight_share == pytest.approx(0.481 * 13 / 12 - 0.519)
    assert c.best_possible_rank == 1
    assert r["robust_candidates"].top1_weight_share.sum() == pytest.approx(1)
    assert r["robust_candidates"].top2_weight_share.sum() == pytest.approx(2)
    np.testing.assert_allclose(
        r["robust_candidates"].worst_regret, [12 / 13, 1.0, 0.519]
    )


def test_equal_scores_do_not_hide_arbitrary_topk_ids():
    d = pd.DataFrame(
        {
            "grid_id": ["C", "B", "A"],
            "static_score": [0.5] * 3,
            "mobility_score": [0.5] * 3,
        }
    )
    r = weight_audit(d, ks=(1,))["robust_candidates"].set_index("grid_id")
    assert r.top1_weight_share.to_dict() == {"A": 1.0, "B": 0.0, "C": 0.0}
    assert r.top1_necessary_share.eq(0).all() and r.top1_possible_share.eq(1).all()
    assert r.best_possible_rank.eq(1).all() and r.worst_possible_rank.eq(3).all()
    assert r.worst_regret.eq(0).all() and r.pareto_efficient.all()


def test_pareto_and_regret_on_restricted_preferences():
    d = pd.DataFrame(
        {
            "grid_id": ["A", "B", "C"],
            "static_score": [1.0, 0.5, 0.0],
            "mobility_score": [1.0, 0.5, 0.0],
        }
    )
    r = weight_audit(d, 0.4, 0.6, ks=(1,))["robust_candidates"]
    assert r.dominated_by_count.tolist() == [0, 1, 2]
    assert r.minimax_regret_choice.tolist() == [True, False, False]
    d.loc[0, "static_score"] = np.nan
    with pytest.raises(ValueError):
        weight_audit(d)


def test_single_candidate_has_no_discriminative_evidence():
    d = pd.DataFrame(
        {"grid_id": ["ONLY"], "static_score": [0.0], "mobility_score": [0.0]}
    )
    result = weight_audit(d)["robust_candidates"].iloc[0]
    assert result.top5_weight_share == 1 and result.worst_regret == 0
    assert result.best_possible_rank == result.worst_possible_rank == 1


def test_specification_audit_constants_and_reference_identity():
    features = pd.DataFrame(
        {
            "grid_id": [str(i) for i in range(12)],
            "population": np.arange(12),
            "poi_count": [7] * 12,
            "vehicle_flow": np.arange(12) ** 2,
        }
    )
    result = specification_audit(features)
    assert (
        result["feature_diagnostics"]
        .set_index("feature")
        .loc["poi_count", "constant_feature"]
    )
    reference = result["specification_comparison"].query(
        "normalization == 'minmax' and population_weight_within_spatial == 0.7"
    )
    assert reference.top_k_overlap.eq(1).all() and np.allclose(reference.spearman, 1)
    assert result["specification_ranks"].integrated_score.between(0, 1).all()


def test_spatial_internal_weight_changes_scores_and_week_blocks_remain_whole():
    b = demo_bundle(days=21)
    r = analyze_bundle(b, bootstrap_n=10, population_weight=0.0, bootstrap_unit="week")
    f = r["scores"]
    expected = (f.poi_count - f.poi_count.min()) / (
        f.poi_count.max() - f.poi_count.min()
    )
    np.testing.assert_allclose(f.static_score, expected)
    reps = r["bootstrap_replicates"]
    assert not reps.empty and reps.resampling_unit.eq("week").all()
    days = pd.Series(sorted(r["daily"].date.unique()))
    blocks = (
        days.groupby(pd.to_datetime(days).dt.to_period("W-SUN").astype(str))
        .agg(list)
        .to_dict()
    )
    for row in reps.itertuples():
        expected_draws = [
            d for block in row.drawn_blocks.split(";") for d in blocks[block]
        ]
        assert row.drawn_days.split(";") == expected_draws
    small = analyze_bundle(demo_bundle(days=5), bootstrap_n=10, bootstrap_unit="week")
    assert small["selection_stability"].empty
    with pytest.raises(ValueError):
        score_aggregate(f, population_weight=np.nan)
