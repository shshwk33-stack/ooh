"""Synthetic source fixtures test guards, not empirical study outcomes."""

import io
from zipfile import ZipFile

import numpy as np
import pandas as pd
import pytest

from transit_ooh.public_sources import (
    DONG,
    NAME,
    QUARTER,
    SECTOR,
    TOTAL,
    build_candidate_features,
    common_reported_sectors,
    evaluate_public_outcomes,
    integer_ids,
    mapo_stores,
    provider_road_aggregates,
    read_seoul_zip,
)


@pytest.fixture
def stores():
    names = {str(11140500 + i): f"서울특별시 마포구 시험{i}동" for i in range(16)}
    data = pd.DataFrame(
        [
            {
                DONG: str(11440500 + i),
                NAME: f"시험{i}동",
                QUARTER: q,
                SECTOR: "CS01",
                TOTAL: i + 3,
                "점포_수": i + 1,
                "프랜차이즈_점포_수": 2,
            }
            for i in range(16)
            for q in [20241, 20242, 20243, 20244]
        ]
    )
    return data, names


def test_total_stock_is_not_double_counted_or_mislabeled_general_stock(stores):
    frame, coverage = mapo_stores(*stores)
    assert len(frame) == 16 and len(coverage) == 64
    assert frame.iloc[0].stores_mean == 3
    assert frame.iloc[0].grid_id == "11140500"
    assert frame.iloc[0].seoul_dong_id == "11440500"


@pytest.mark.parametrize(
    "problem", ["quarter", "year", "duplicate", "name", "identity", "negative"]
)
def test_incompatible_commercial_support_is_rejected(stores, problem):
    data, names = stores
    if problem == "quarter":
        data = data.iloc[1:]
    elif problem == "year":
        data.loc[0, QUARTER] = 20251
    elif problem == "duplicate":
        data = pd.concat([data, data.iloc[:1]])
    elif problem == "name":
        data.loc[data[DONG].eq("11440500"), NAME] = "다른동"
    elif problem == "identity":
        data.loc[0, TOTAL] = 9
    else:
        data.loc[0, TOTAL] = -1
    with pytest.raises(ValueError):
        mapo_stores(data, names)


@pytest.mark.parametrize("value", [11140500.5, np.nan, np.inf, True, -1, 2**53])
def test_invalid_numeric_identifiers_are_rejected(value):
    with pytest.raises(ValueError):
        integer_ids(pd.Series([value]))


def test_integral_float_identifier_matches_string_key():
    assert integer_ids(pd.Series([11140500.0])).iloc[0] == "11140500"


@pytest.fixture
def road_inputs():
    roads = pd.DataFrame(
        {
            "link_id": [1, 2, 3],
            "length_km": [1.0, 3.0, 2.0],
            "road_class": ["시군도", "시군도", "도시고속도로"],
            "all_vehicles_per_day": [10.0, 30.0, 100.0],
            "trucks_per_day": [2.0, 6.0, 10.0],
        }
    )
    network = pd.DataFrame(
        {
            "k_link_id": [1.0, 2.0, 3.0],
            "k_length": [1.0, 3.0, 2.0],
            "emd_id": [11140500, 11140500, 11140501],
            "sigungu_id": [11140] * 3,
        }
    )
    metadata = {
        "year": 2024,
        "day_type": "평일",
        "statistic": "annual_average_day",
        "network": {"network_sha256": "fixture"},
    }
    return roads, network, metadata


def test_length_weighting_and_missing_local_roads_are_not_zero(road_inputs):
    roads, network, metadata = road_inputs
    output, mapping = provider_road_aggregates(roads, network, metadata, "fixture")
    assert len(mapping) == 3
    assert output.iloc[0].traffic_all_local == 25
    assert output.iloc[0].traffic_truck_local == 5
    assert np.isnan(output.iloc[1].traffic_all_local)


@pytest.mark.parametrize(
    "problem", ["hash", "length", "unmatched", "duplicate", "year", "day"]
)
def test_incompatible_road_context_is_rejected(road_inputs, problem):
    roads, network, metadata = road_inputs
    if problem == "hash":
        metadata["network"]["network_sha256"] = "changed"
    elif problem == "length":
        network.loc[0, "k_length"] = 99
    elif problem == "unmatched":
        roads.loc[0, "link_id"] = 99
    elif problem == "duplicate":
        network = pd.concat([network, network.iloc[:1]])
    elif problem == "year":
        metadata["year"] = 2023
    else:
        metadata["day_type"] = "주말"
    with pytest.raises(ValueError):
        provider_road_aggregates(roads, network, metadata, "fixture")


def test_no_context_is_ineligible_but_observed_zero_remains_eligible(
    stores, road_inputs
):
    roads, network, metadata = road_inputs
    roads.loc[:1, ["all_vehicles_per_day", "trucks_per_day"]] = 0
    features, coverage, _, _ = build_candidate_features(
        *stores, roads, network, metadata, "fixture"
    )
    assert len(features) == 1 and features.iloc[0].traffic_all_local == 0
    assert coverage.eligible.sum() == 1
    assert coverage.traffic_all_local.isna().sum() == 15


def test_zip_reader_is_bounded_and_preserves_korean_ids():
    raw = io.BytesIO()
    with ZipFile(raw, "w") as archive:
        archive.writestr(
            "data.csv", f"{DONG},{NAME}\n11440500,시험동\n".encode("cp949")
        )
    raw.seek(0)
    assert read_seoul_zip(raw).iloc[0][DONG] == "11440500"
    raw.seek(0)
    with pytest.raises(ValueError, match="bounded"):
        read_seoul_zip(raw, max_uncompressed=1)


@pytest.fixture
def outcomes():
    features = pd.DataFrame(
        {
            "grid_id": ["b", "a", "c"],
            "seoul_dong_id": ["11440501", "11440502", "11440503"],
            "name": ["갑", "을", "병"],
        }
    )
    sales = pd.DataFrame(
        [
            {
                DONG: code,
                NAME: name,
                QUARTER: q,
                SECTOR: "CS01",
                "당월_매출_건수": value,
            }
            for code, name, value in zip(
                features.seoul_dong_id, features.name, [10, 20, 30], strict=True
            )
            for q in [20251, 20252, 20253, 20254]
        ]
    )
    return sales, features


def test_transaction_association_preserves_order_and_set_only_r_has_no_ranking(
    outcomes,
):
    sales, features = outcomes
    result, values = evaluate_public_outcomes(
        sales, features, {"A": [1, 2, 3]}, {"A": [0], "R": [2]}
    )
    assert result.loc[result.model.eq("A"), "spearman"].eq(1).all()
    assert result.loc[result.model.eq("R"), "spearman"].isna().all()
    assert (
        result.loc[result.model.eq("A"), "selected_transaction_share"].eq(1 / 6).all()
    )
    assert (
        result.loc[result.model.eq("R"), "selected_transaction_share"].eq(1 / 2).all()
    )
    assert values.iloc[:3].grid_id.tolist() == ["b", "a", "c"]
    assert common_reported_sectors(sales, features) == ["CS01"]


def test_constant_outcomes_or_score_has_undefined_correlation(outcomes):
    sales, features = outcomes
    sales["당월_매출_건수"] = 10
    result, _ = evaluate_public_outcomes(sales, features, {"A": [1, 2, 3]}, {"A": [0]})
    assert result.spearman.isna().all()


@pytest.mark.parametrize(
    "problem",
    [
        "missing",
        "duplicate",
        "name",
        "year",
        "negative",
        "different_k",
        "selection_float",
        "score_length",
    ],
)
def test_outcome_support_errors_are_not_silently_filled_or_realigned(outcomes, problem):
    sales, features = outcomes
    scores, selected = {"A": [1, 2, 3]}, {"A": [0]}
    if problem == "missing":
        sales = sales.iloc[1:]
    elif problem == "duplicate":
        sales = pd.concat([sales, sales.iloc[:1]])
    elif problem == "name":
        sales.loc[0, NAME] = "다른동"
    elif problem == "year":
        sales.loc[0, QUARTER] = 20261
    elif problem == "negative":
        sales.loc[0, "당월_매출_건수"] = -1
    elif problem == "different_k":
        selected["R"] = [0, 1]
    elif problem == "selection_float":
        selected["A"] = [0.5]
    else:
        scores["A"] = [1, 2]
    with pytest.raises(ValueError):
        evaluate_public_outcomes(sales, features, scores, selected)
