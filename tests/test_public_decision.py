"""Analytical and independent brute-force fixtures, not empirical outcomes."""

import itertools
import math

import numpy as np
import pandas as pd
import pytest

from transit_ooh.public_decision import (
    build_scenarios,
    compare_portfolios,
    nominal_scores,
    normalize,
    portfolio_metrics,
    solve_portfolio,
    top_indices,
)


@pytest.fixture
def features():
    f = pd.DataFrame({"grid_id": ["B", "A", "C"], "name": ["을", "갑", "병"]})
    for q in [20241, 20242, 20243, 20244, "mean"]:
        f[f"stores_{q}"] = [1.0, 2.0, 3.0]
    for scope in ["all", "local"]:
        for kind in ["all", "truck"]:
            f[f"traffic_{kind}_{scope}"] = [3.0, 2.0, 1.0]
    return f


def test_joint_selection_differs_from_top_k_individual_minimax_candidates():
    v = np.array([[1, 0.6, 0], [0, 0.6, 1]])
    one = solve_portfolio(v, 1)
    pair = solve_portfolio(v, 2)
    assert one["selected"].tolist() == [1]
    assert pair["selected"].tolist() == [0, 2]
    assert pair["worst_regret"] == pytest.approx(0.3)
    assert pair["combinations_evaluated"] == 3


@pytest.mark.parametrize("n,k", [(1, 1), (4, 1), (4, 2), (6, 3), (6, 6)])
def test_vectorized_solver_matches_independent_scalar_brute_force(n, k):
    v = np.random.default_rng(73 + n + k).random((7, n))
    choices = list(itertools.combinations(range(n), k))
    # Deliberately avoid the solver's sorted-oracle and array indexing paths.
    utility = [
        [sum(float(row[i]) for i in choice) / k for choice in choices] for row in v
    ]
    expected = [max(max(row) - row[j] for row in utility) for j in range(len(choices))]
    result = solve_portfolio(v, k)
    np.testing.assert_allclose(result["all_worst_regrets"], expected, atol=1e-14)
    assert result["worst_regret"] == pytest.approx(min(expected), abs=1e-14)
    assert tuple(result["selected"]) == choices[int(np.argmin(expected))]


def test_closed_interval_endpoints_cover_dense_continuous_regret():
    a = np.array([1, 0.2, 0.7, 0.3])
    b = np.array([0.1, 0.9, 0.4, 0.8])
    endpoints = np.array([0.2 * b + 0.8 * a, 0.8 * b + 0.2 * a])
    dense = np.array([w * b + (1 - w) * a for w in np.linspace(0.2, 0.8, 1001)])
    for selected in itertools.combinations(range(4), 2):
        assert portfolio_metrics(endpoints, selected)["worst_regret"] == pytest.approx(
            portfolio_metrics(dense, selected)["worst_regret"]
        )


def test_all_ties_expose_all_optima_and_no_false_unique_winner():
    result = solve_portfolio(np.zeros((3, 4)), 2)
    assert result["optimal_sets"] == math.comb(4, 2)
    assert result["selected"].tolist() == [0, 1]
    assert result["possible"].tolist() == [0, 1, 2, 3]
    assert result["necessary"].tolist() == []
    assert result["optimal_combinations"].tolist() == list(
        map(list, itertools.combinations(range(4), 2))
    )
    assert result["worst_regret"] == 0


@pytest.mark.parametrize(
    "values,k",
    [
        ([[np.nan, 0]], 1),
        ([[np.inf, 0]], 1),
        ([[2, 0]], 1),
        ([[-0.1, 0]], 1),
        ([], 1),
        ([[]], 1),
        ([0.2, 0.5], 1),
        ([[0.2, 0.5]], True),
        ([[0.2, 0.5]], 1.0),
        ([[0.2, 0.5]], 0),
        ([[0.2, 0.5]], 3),
    ],
)
def test_invalid_matrix_or_k_are_rejected(values, k):
    with pytest.raises(ValueError):
        solve_portfolio(values, k)


def test_enumeration_budget_prevents_unbounded_allocation():
    with pytest.raises(ValueError, match="budget"):
        solve_portfolio(np.ones((2, 30)), 15)
    with pytest.raises(ValueError, match="budget"):
        solve_portfolio(np.zeros((1, 10_000)), 9_999)


@pytest.mark.parametrize("selected", [[-1], [2], [0, 0], [0.2], [True], [], [[0]]])
def test_metrics_reject_invalid_selection_without_silent_indexing(selected):
    with pytest.raises(ValueError):
        portfolio_metrics([[0.2, 0.8]], selected)


def test_tied_and_constant_normalization_and_stable_selection():
    np.testing.assert_allclose(normalize([4, 4, 8], "percentile"), [0, 0, 1])
    for method in ["minmax", "log1p_minmax", "percentile"]:
        np.testing.assert_array_equal(normalize([4, 4], method), [0, 0])
    np.testing.assert_allclose(normalize([0, 3, 15], "log1p_minmax"), [0, 0.5, 1])
    assert top_indices([0.5, 0.5, 0.1], 1).tolist() == [0]
    with pytest.raises(ValueError):
        normalize([1, 1], "unknown")
    with pytest.raises(ValueError):
        normalize([-1, 0])


def test_scenario_design_and_future_outcome_noninterference(features):
    f, design, values = build_scenarios(features)
    assert f.grid_id.tolist() == ["A", "B", "C"]
    assert values.shape == (120, 3)
    assert set(design.alpha) == {0, 1}
    assert set(design.normalization) == {"minmax", "log1p_minmax", "percentile"}
    assert values.min() == 0 and values.max() == 1
    features["future_transactions"] = [1e20, 0, -1e20]
    np.testing.assert_array_equal(build_scenarios(features)[2], values)
    assert build_scenarios(features, 0.5, 0.5)[2].shape == (60, 3)


@pytest.mark.parametrize("problem", ["duplicate_id", "negative", "nan", "column"])
def test_incompatible_candidate_support_is_rejected(features, problem):
    if problem == "duplicate_id":
        features.loc[0, "grid_id"] = "A"
    elif problem == "negative":
        features.loc[0, "stores_mean"] = -1
    elif problem == "nan":
        features.loc[0, "traffic_all_all"] = np.nan
    else:
        features = features.drop(columns="stores_20241")
    with pytest.raises(ValueError):
        build_scenarios(features)


def test_scores_weight_extremes_and_comparison_share_candidate_support(features):
    at_zero = nominal_scores(features, 0)
    at_one = nominal_scores(features, 1)
    assert at_zero.grid_id.tolist() == features.grid_id.tolist()
    np.testing.assert_allclose(at_zero.integrated_score, at_zero.static_score)
    np.testing.assert_allclose(at_one.integrated_score, at_one.mobility_score)
    study = compare_portfolios(features, k=2)
    assert study["features"].grid_id.tolist() == ["A", "B", "C"]
    assert set(study["comparison"].model) == {
        "A_stores",
        "B_vehicle_context",
        "C50_reduced",
        "C60_reduced",
        "R_minimax",
    }
    assert all(len(selection) == 2 for selection in study["selections"].values())
    assert study["comparison"].worst_regret.min() == pytest.approx(
        study["solver"]["worst_regret"]
    )
