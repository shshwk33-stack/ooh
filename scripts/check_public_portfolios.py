"""Independently audit the primary K=5, full-weight public study from CSVs.

Uses only Python's standard library and never imports the portfolio solver,
NumPy, institutional raw files, or 2025 outcomes. Scalar fsum/nlargest utilities
check every exported K-set. Failure exits nonzero and records no passing result.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import heapq
import itertools
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path

K = 5
TOLERANCE = 1e-12


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_table(path, required=()):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames
        require(
            fields and all(fields) and len(set(fields)) == len(fields),
            f"Invalid or duplicate CSV headers: {path.name}",
        )
        require(set(required) <= set(fields), f"Missing columns: {path.name}")
        rows = list(reader)
    require(rows, f"Empty CSV: {path.name}")
    require(
        all(
            None not in row and all(value is not None for value in row.values())
            for row in rows
        ),
        f"Malformed CSV rows: {path.name}",
    )
    return fields, rows


def finite(value, label, unit=False):
    value = float(value)
    require(math.isfinite(value), f"Nonfinite number: {label}")
    if unit:
        require(0 <= value <= 1, f"Score outside [0,1]: {label}")
    return value


def integer(value, label):
    value = finite(value, label)
    require(value >= 0 and value.is_integer(), f"Invalid integer: {label}")
    return int(value)


def selected_key(value, ids):
    chosen = value.split(";")
    require(
        len(chosen) == K and len(set(chosen)) == K and set(chosen) <= set(ids),
        "Selection must contain exactly five distinct eligible IDs",
    )
    return tuple(sorted(chosen))


def close(actual, expected, label):
    actual = finite(actual, label)
    require(abs(actual - expected) <= TOLERANCE, f"Numeric mismatch: {label}")
    return abs(actual - expected)


def minmax(values):
    low, high = min(values), max(values)
    return (
        [0.0] * len(values)
        if low == high
        else [(x - low) / (high - low) for x in values]
    )


def normalized(values, method):
    require(min(values) >= 0, "Negative context feature")
    if method == "log1p_minmax":
        values = [math.log1p(value) for value in values]
    elif method == "percentile":
        values = [
            sum(other < value for other in values)
            + (sum(other == value for other in values) + 1) / 2
            for value in values
        ]
    elif method != "minmax":
        raise ValueError("Unknown scenario normalization")
    return minmax(values)


def audit(report):
    tables = report / "tables"
    names = [
        "candidate_features",
        "scenario_scores",
        "scenario_design",
        "nominal_scores",
        "all_portfolios_tradeoff",
        "portfolio_comparison",
        "all_optimal_sets",
        "price_of_robustness",
    ]
    paths = {name: tables / f"{name}.csv" for name in names}
    _, features = read_table(
        paths["candidate_features"], ["grid_id", "stores_mean", "traffic_all_local"]
    )
    ids = [row["grid_id"] for row in features]
    require(
        ids == sorted(ids) and len(set(ids)) == len(ids),
        "Candidate IDs must be unique and lexical",
    )
    require(len(ids) >= K, "Too few eligible candidates for K=5")
    count = math.comb(len(ids), K)
    require(count <= 100_000, "Independent exhaustive-check budget exceeded")

    headers, score_rows = read_table(paths["scenario_scores"], ["scenario_id", *ids])
    require(set(headers) == {"scenario_id", *ids}, "Unexpected scenario score columns")
    require(
        [key for key in headers if key != "scenario_id"] == ids,
        "Scenario candidate order differs",
    )
    require(
        len(score_rows) == 120, "Primary full-weight study must have 120 design rows"
    )
    scenario_ids = [integer(row["scenario_id"], "scenario_id") for row in score_rows]
    require(
        scenario_ids == list(range(120)), "Scenario IDs are incomplete or reordered"
    )
    matrix = [
        [finite(row[id_], f"scenario {i}/{id_}", unit=True) for id_ in ids]
        for i, row in enumerate(score_rows)
    ]

    _, design = read_table(
        paths["scenario_design"],
        ["scenario_id", "stock", "road", "normalization", "alpha"],
    )
    require(len(design) == 120, "Incomplete scenario design")
    require(
        [integer(row["scenario_id"], "design ID") for row in design] == scenario_ids,
        "Design and score rows disagree",
    )
    stock_definitions = [f"stores_{q}" for q in [20241, 20242, 20243, 20244]] + [
        "stores_mean"
    ]
    road_definitions = [
        f"traffic_{kind}_{scope}"
        for scope in ["all", "local"]
        for kind in ["all", "truck"]
    ]
    definitions = [
        (
            row["stock"],
            row["road"],
            row["normalization"],
            finite(row["alpha"], "alpha", unit=True),
        )
        for row in design
    ]
    expected_design = set(
        itertools.product(
            stock_definitions,
            road_definitions,
            ["minmax", "log1p_minmax", "percentile"],
            [0.0, 1.0],
        )
    )
    require(
        len(set(definitions)) == 120 and set(definitions) == expected_design,
        "Unexpected primary scenario definitions",
    )

    # Reconstruct every scenario from the acquired feature table independently
    # of build_scenarios and pandas' rank/normalization implementations.
    differences = []
    for row_index, (stock, road, method, alpha) in enumerate(definitions):
        a_values = normalized([finite(row[stock], stock) for row in features], method)
        b_values = normalized([finite(row[road], road) for row in features], method)
        for i, (a_value, b_value) in enumerate(zip(a_values, b_values, strict=True)):
            expected = (1 - alpha) * a_value + alpha * b_value
            differences.append(
                close(matrix[row_index][i], expected, "reconstructed scenario score")
            )

    choices = list(itertools.combinations(range(len(ids)), K))
    keys = [tuple(ids[i] for i in chosen) for chosen in choices]
    oracle = [math.fsum(heapq.nlargest(K, row)) / K for row in matrix]
    metrics = {}
    for key, chosen in zip(keys, choices, strict=True):
        utilities = [math.fsum(row[i] for i in chosen) / K for row in matrix]
        regrets = [
            max(best - value, 0.0)
            for best, value in zip(oracle, utilities, strict=True)
        ]
        metrics[key] = {
            "worst_regret": max(regrets),
            "mean_scenario_regret": math.fsum(regrets) / len(regrets),
            "minimum_scenario_utility": min(utilities),
        }
    worst = [metrics[key]["worst_regret"] for key in keys]
    optimum = min(worst)
    optima = [
        key for key in keys if abs(metrics[key]["worst_regret"] - optimum) <= TOLERANCE
    ]

    # Independently reconstruct basic min-max scores from acquired feature CSV.
    raw_a = [finite(row["stores_mean"], "stores_mean") for row in features]
    raw_b = [finite(row["traffic_all_local"], "traffic_all_local") for row in features]
    require(min(raw_a) >= 0 and min(raw_b) >= 0, "Negative acquired context feature")
    a, b = minmax(raw_a), minmax(raw_b)
    c50 = [(x + y) / 2 for x, y in zip(a, b, strict=True)]
    c60 = [0.4 * x + 0.6 * y for x, y in zip(a, b, strict=True)]
    _, nominal = read_table(
        paths["nominal_scores"],
        ["grid_id", "static_score", "mobility_score", "integrated_score"],
    )
    require(
        [row["grid_id"] for row in nominal] == ids, "Nominal candidate support differs"
    )
    for i, row in enumerate(nominal):
        for column, expected in [
            ("static_score", a[i]),
            ("mobility_score", b[i]),
            ("integrated_score", c50[i]),
        ]:
            differences.append(
                close(row[column], expected, f"nominal {column}/{ids[i]}")
            )
    utility_by_key = {
        key: math.fsum(c50[i] for i in chosen) / K
        for key, chosen in zip(keys, choices, strict=True)
    }
    nominal_oracle = math.fsum(heapq.nlargest(K, c50)) / K

    _, portfolios = read_table(
        paths["all_portfolios_tradeoff"],
        [
            "selected_ids",
            "worst_regret",
            "nominal_mean_utility",
            "pareto_representative",
        ],
    )
    exported = {}
    for row in portfolios:
        key = selected_key(row["selected_ids"], ids)
        require(key not in exported, "Duplicate exported portfolio")
        require(
            row["pareto_representative"] in {"True", "False"}, "Invalid Pareto boolean"
        )
        exported[key] = row
    require(set(exported) == set(keys), "Exported portfolio set is incomplete")
    for key in keys:
        differences.append(
            close(
                exported[key]["worst_regret"],
                metrics[key]["worst_regret"],
                "portfolio worst regret",
            )
        )
        differences.append(
            close(
                exported[key]["nominal_mean_utility"],
                utility_by_key[key],
                "portfolio nominal utility",
            )
        )

    # Independent O(number_of_sets^2) dominance test, not sorted-frontier code.
    nondominated = []
    for key in keys:
        utility, regret = utility_by_key[key], metrics[key]["worst_regret"]
        dominated = any(
            utility_by_key[other] >= utility - TOLERANCE
            and metrics[other]["worst_regret"] <= regret + TOLERANCE
            and (
                utility_by_key[other] > utility + TOLERANCE
                or metrics[other]["worst_regret"] < regret - TOLERANCE
            )
            for other in keys
        )
        if not dominated:
            nondominated.append(key)
    marked = [key for key in keys if exported[key]["pareto_representative"] == "True"]
    require(
        set(marked) <= set(nondominated),
        "Dominated portfolio marked as Pareto representative",
    )
    require(
        all(
            any(
                abs(utility_by_key[key] - utility_by_key[other]) <= TOLERANCE
                and abs(metrics[key]["worst_regret"] - metrics[other]["worst_regret"])
                <= TOLERANCE
                for other in marked
            )
            for key in nondominated
        ),
        "Unrepresented Pareto coordinates",
    )

    def top(values):
        indices = sorted(
            range(len(ids)), key=lambda i: (-round(values[i], 14), ids[i])
        )[:K]
        return tuple(sorted(ids[i] for i in indices))

    model_keys = {
        "A_stores": top(a),
        "B_vehicle_context": top(b),
        "C50_reduced": top(c50),
        "C60_reduced": top(c60),
        "R_minimax": optima[0],
    }
    _, comparisons = read_table(
        paths["portfolio_comparison"],
        [
            "model",
            "k",
            "weight_low",
            "weight_high",
            "selected_ids",
            *next(iter(metrics.values())),
        ],
    )
    primary = [
        row
        for row in comparisons
        if integer(row["k"], "K") == K
        and finite(row["weight_low"], "low") == 0
        and finite(row["weight_high"], "high") == 1
    ]
    require(
        len(primary) == len(model_keys)
        and {row["model"] for row in primary} == set(model_keys),
        "Incomplete or duplicate primary model comparisons",
    )
    for row in primary:
        key = selected_key(row["selected_ids"], ids)
        require(
            key == model_keys[row["model"]],
            f"Unexpected baseline/lexical robust selection: {row['model']}",
        )
        for metric, expected in metrics[key].items():
            differences.append(
                close(row[metric], expected, f"primary {row['model']}/{metric}")
            )

    _, optimal_rows = read_table(
        paths["all_optimal_sets"],
        ["model", "selected_ids", *next(iter(metrics.values()))],
    )
    require(
        [selected_key(row["selected_ids"], ids) for row in optimal_rows] == optima,
        "Missing or reordered optimal alternatives",
    )
    require(
        len({row["model"] for row in optimal_rows}) == len(optimal_rows),
        "Duplicate optimum model name",
    )
    for row in optimal_rows:
        key = selected_key(row["selected_ids"], ids)
        model_keys[row["model"]] = key
        for metric, expected in metrics[key].items():
            differences.append(
                close(row[metric], expected, f"optimal alternative/{metric}")
            )

    _, prices = read_table(
        paths["price_of_robustness"],
        [
            "model",
            "nominal_mean_utility",
            "nominal_loss_vs_C50",
            *next(iter(metrics.values())),
        ],
    )
    require(
        len(prices) == len(model_keys)
        and {row["model"] for row in prices} == set(model_keys),
        "Incomplete or duplicate robustness-price models",
    )
    for row in prices:
        key = model_keys[row["model"]]
        differences.append(
            close(
                row["nominal_mean_utility"],
                utility_by_key[key],
                "price nominal utility",
            )
        )
        differences.append(
            close(
                row["nominal_loss_vs_C50"],
                nominal_oracle - utility_by_key[key],
                "price loss vs C50",
            )
        )
        for metric, expected in metrics[key].items():
            differences.append(close(row[metric], expected, f"price/{metric}"))

    return {
        "status": "passed",
        "checked_at_utc": datetime.now(UTC).isoformat(),
        "report_directory": str(report),
        "scope": "primary_K5_full_weight_range_only_not_advertising_outcome_validation",
        "implementation": "Python standard library math.fsum + heapq.nlargest + pairwise dominance; no portfolio solver imports",
        "future_outcome_files_read": False,
        "scenario_rows": len(matrix),
        "candidates": len(ids),
        "k": K,
        "sets_independently_evaluated": count,
        "maximum_absolute_numeric_difference": max(differences),
        "tolerance": TOLERANCE,
        "minimum_worst_regret": optimum,
        "optimal_sets": len(optima),
        "optimal_ids": optima,
        "frontier_representatives": len(marked),
        "nondominated_portfolios": len(nondominated),
        "false_frontier_representatives": 0,
        "uncovered_frontier_coordinates": 0,
        "input_sha256": {
            str(path.relative_to(report)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in paths.values()
        },
        "checker_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=Path("reports/public_decision"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/runs/public_independent_check.json"),
    )
    args = parser.parse_args()
    try:
        result = audit(args.report)
    except (OSError, ValueError, KeyError) as exc:
        result = {
            "status": "failed",
            "checked_at_utc": datetime.now(UTC).isoformat(),
            "error": str(exc),
            "report_directory": str(args.report),
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps(result, ensure_ascii=False), file=sys.stderr)
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
