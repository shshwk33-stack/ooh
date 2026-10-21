"""Exact minimax-regret selection of aggregate public-data candidate regions.

Minimax regret is an established decision method. This module applies it to a
fixed set of normalized context scenarios; it does not estimate advertising
outcomes, probabilities, delivery stops, or feasible vehicle routes.
"""

from __future__ import annotations

import itertools
import math

import numpy as np
import pandas as pd

METHODS = ("minmax", "log1p_minmax", "percentile")
STOCKS = (
    *(f"stores_{quarter}" for quarter in (20241, 20242, 20243, 20244)),
    "stores_mean",
)
ROADS = tuple(
    f"traffic_{kind}_{scope}" for scope in ("all", "local") for kind in ("all", "truck")
)


def _integer(value, name, minimum=1):
    if (
        isinstance(value, (bool, np.bool_))
        or not isinstance(value, (int, np.integer))
        or value < minimum
    ):
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return int(value)


def _vector(values):
    try:
        values = np.asarray(values, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError("Require a finite numeric vector") from exc
    if values.ndim != 1 or not len(values) or not np.isfinite(values).all():
        raise ValueError("Require a nonempty finite numeric vector")
    return values


def _unit_matrix(values):
    try:
        values = np.asarray(values, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError("Require a finite unit-range scenario matrix") from exc
    if (
        values.ndim != 2
        or not all(values.shape)
        or not np.isfinite(values).all()
        or (values < 0).any()
        or (values > 1).any()
    ):
        raise ValueError("Scenario matrix must be nonempty, finite, within [0,1]")
    return values


def _candidates(features, columns):
    required = {"grid_id", "name", *columns}
    if not required <= set(features):
        raise ValueError("Missing required candidate identifiers or context features")
    f = features.copy()
    if not len(f) or f[["grid_id", "name"]].isna().any().any():
        raise ValueError("Require nonempty candidates and complete identifiers")
    f["grid_id"] = f.grid_id.astype(str).str.strip()
    if f.grid_id.eq("").any() or f.grid_id.duplicated().any():
        raise ValueError("Unique nonempty candidate IDs required")
    values = f[list(columns)].apply(pd.to_numeric, errors="raise")
    if not np.isfinite(values.to_numpy(dtype=float)).all() or (values < 0).any().any():
        raise ValueError("Context features must be finite and nonnegative")
    f[list(columns)] = values
    return f


def normalize(values, method="minmax"):
    """Transform within the fixed candidate set; constants carry zero contrast.

    Percentile uses average tie ranks followed by observed-range scaling. A zero
    normalized score means no relative contrast here, not absence of activity.
    """
    if method not in METHODS:
        raise ValueError(f"Unknown normalization: {method}")
    a = _vector(values)
    if (a < 0).any():
        raise ValueError("Context values must be nonnegative")
    if np.ptp(a) == 0:
        return np.zeros(len(a), dtype=float)
    if method == "log1p_minmax":
        a = np.log1p(a)
    elif method == "percentile":
        a = pd.Series(a).rank(method="average").to_numpy()
    return (a - a.min()) / np.ptp(a)


def build_scenarios(features, low=0.0, high=1.0):
    """Return ordered features, scenario definitions, and endpoint score matrix.

    For a fixed representation, scenario regret is convex in the linear weight,
    so its maximum on the closed interval occurs at an endpoint. Rows are a
    design, not independent samples or draws from a probability distribution.
    """
    if not np.isfinite([low, high]).all() or not 0 <= low <= high <= 1:
        raise ValueError("Require 0 <= low <= high <= 1")
    f = _candidates(features, (*STOCKS, *ROADS))
    f = f.sort_values("grid_id").reset_index(drop=True)
    definitions, scores = [], []
    for stock, road, method, alpha in itertools.product(
        STOCKS, ROADS, METHODS, sorted({float(low), float(high)})
    ):
        a, b = normalize(f[stock], method), normalize(f[road], method)
        scores.append((1 - alpha) * a + alpha * b)
        definitions.append(
            {"stock": stock, "road": road, "normalization": method, "alpha": alpha}
        )
    return f, pd.DataFrame(definitions), np.asarray(scores)


def nominal_scores(features, alpha=0.5, method="minmax"):
    """Reduced two-source scores, preserving the supplied candidate order."""
    if not np.isfinite(alpha) or not 0 <= alpha <= 1:
        raise ValueError("Weight must be finite within [0,1]")
    f = _candidates(features, ("stores_mean", "traffic_all_local"))
    a, b = normalize(f.stores_mean, method), normalize(f.traffic_all_local, method)
    return pd.DataFrame(
        {
            "grid_id": f.grid_id.to_numpy(),
            "static_score": a,
            "mobility_score": b,
            "integrated_score": (1 - alpha) * a + alpha * b,
        }
    )


def top_indices(values, k):
    """Descending utility, preserving input order for 14-decimal score ties."""
    a = _vector(values)
    k = _integer(k, "K")
    if k > len(a):
        raise ValueError("K exceeds the candidate count")
    return np.argsort(-np.round(a, 14), kind="stable")[:k]


def solve_portfolio(scenarios, k, max_combinations=100_000):
    """Enumerate all K-sets and expose every optimum within 1e-12 tolerance.

    The scenario oracle is its best K-set mean utility. Lexical candidate order
    supplied by build_scenarios breaks ties reproducibly, not substantively.
    No outcome label or future performance target is accepted by this solver.
    """
    v = _unit_matrix(scenarios)
    k = _integer(k, "K")
    max_combinations = _integer(max_combinations, "Enumeration budget")
    n = v.shape[1]
    if k > n:
        raise ValueError("K exceeds the candidate count")
    count = math.comb(n, k)
    if count > max_combinations or count * k > 5_000_000:
        raise ValueError("Candidate set exceeds exhaustive search budget")
    combinations = np.asarray(list(itertools.combinations(range(n), k)), dtype=int)
    oracle = np.sort(v, axis=1)[:, -k:].mean(axis=1)
    worst = np.zeros(count)
    # Bound score temporaries even when a legal combination count has large K.
    batch = max(1, min(24, 2_000_000 // (count * k)))
    for start in range(0, len(v), batch):
        utility = v[start : start + batch, combinations].mean(axis=2)
        worst = np.maximum(
            worst, (oracle[start : start + batch, None] - utility).max(axis=0)
        )
    optimal_indices = np.flatnonzero(np.isclose(worst, worst.min(), rtol=0, atol=1e-12))
    optimal_combinations = combinations[optimal_indices]
    selected = optimal_combinations[0]
    return {
        "selected": selected,
        "worst_regret": float(worst[optimal_indices[0]]),
        "optimal_sets": len(optimal_indices),
        "combinations_evaluated": count,
        "possible": np.unique(optimal_combinations),
        "necessary": np.asarray(
            sorted(set.intersection(*map(set, optimal_combinations))), dtype=int
        ),
        "optimal_combinations": optimal_combinations,
        "oracle": oracle,
        "all_combinations": combinations,
        "all_worst_regrets": worst,
    }


def portfolio_metrics(scenarios, selected):
    """Regret and utility on the supplied scenario design, not outcome accuracy."""
    v = _unit_matrix(scenarios)
    raw = np.asarray(selected)
    if (
        raw.ndim != 1
        or not len(raw)
        or raw.dtype.kind not in "iu"
        or len(set(raw)) != len(raw)
        or (raw < 0).any()
        or (raw >= v.shape[1]).any()
    ):
        raise ValueError("Require nonempty unique in-range integer selections")
    chosen = raw.astype(int)
    oracle = np.sort(v, axis=1)[:, -len(chosen) :].mean(axis=1)
    utility = v[:, chosen].mean(axis=1)
    regret = np.maximum(oracle - utility, 0)
    return {
        "worst_regret": float(regret.max()),
        "mean_scenario_regret": float(regret.mean()),
        "minimum_scenario_utility": float(utility.min()),
    }


def compare_portfolios(features, k=5, low=0.0, high=1.0):
    """Compare A, B, fixed-weight reduced C, and joint minimax K-set selection."""
    f, design, matrix = build_scenarios(features, low, high)
    nominal = nominal_scores(f)
    solved = solve_portfolio(matrix, k)
    selections = {
        "A_stores": top_indices(nominal.static_score, k),
        "B_vehicle_context": top_indices(nominal.mobility_score, k),
        "C50_reduced": top_indices(nominal.integrated_score, k),
        "C60_reduced": top_indices(nominal_scores(f, 0.6).integrated_score, k),
        "R_minimax": solved["selected"],
    }
    comparison = pd.DataFrame(
        [
            {
                "model": model,
                "k": k,
                "weight_low": low,
                "weight_high": high,
                "selected_ids": ";".join(f.iloc[selected].grid_id),
                "selected_names": ";".join(f.iloc[selected]["name"].astype(str)),
                **portfolio_metrics(matrix, selected),
            }
            for model, selected in selections.items()
        ]
    )
    return {
        "features": f,
        "design": design,
        "matrix": matrix,
        "selections": selections,
        "comparison": comparison,
        "solver": solved,
    }
