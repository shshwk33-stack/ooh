"""Reviewed support of acquired aggregate data, kept separate from delivery GPS.

Road context uses provider-assigned dong codes, not invented polygon allocation.
Quarterly stores are stocks; annual traffic is context, not independent daily data.
"""

from __future__ import annotations

import io
from zipfile import ZipFile

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

QUARTER = "기준_년분기_코드"
DONG = "행정동_코드"
NAME = "행정동_코드_명"
SECTOR = "서비스_업종_코드"
TOTAL = "유사_업종_점포_수"


def read_seoul_zip(path, max_uncompressed=150_000_000):
    """Read a single bounded provider CSV in memory, without extracting paths."""
    with ZipFile(path) as archive:
        files = [f for f in archive.infolist() if f.filename.lower().endswith(".csv")]
        if len(files) != 1 or files[0].file_size > max_uncompressed:
            raise ValueError("Require exactly one bounded Seoul CSV")
        raw = archive.read(files[0])
    for encoding in ("utf-8-sig", "cp949"):
        try:
            return pd.read_csv(io.BytesIO(raw), encoding=encoding, dtype={DONG: str})
        except UnicodeDecodeError:
            continue
    raise ValueError("Unsupported provider CSV encoding")


def integer_ids(series):
    """Convert integral provider numbers without appending decimal-zero suffixes."""
    if series.map(lambda x: isinstance(x, (bool, np.bool_))).any():
        raise ValueError("Boolean identifier")
    numbers = pd.to_numeric(series, errors="raise")
    if (
        not np.isfinite(numbers).all()
        or (numbers % 1 != 0).any()
        or (numbers < 0).any()
        or (numbers >= 2**53).any()
    ):
        raise ValueError("Identifiers must be finite, nonnegative exact integers")
    return numbers.astype("int64").astype(str)


def finite_nonnegative(frame, columns, integer=False):
    if frame[columns].map(lambda x: isinstance(x, (bool, np.bool_))).any().any():
        raise ValueError("Boolean measurement")
    values = frame[columns].apply(pd.to_numeric, errors="raise")
    array = values.to_numpy(dtype=float)
    if (
        not np.isfinite(array).all()
        or (array < 0).any()
        or (integer and (array % 1 != 0).any())
    ):
        raise ValueError("Invalid nonnegative numeric measurement")
    return values


def mapo_stores(stores, names):
    """Validate one-to-one 2024 Mapo name/code support and aggregate reported stock.

    Official API names SIMILR_INDUTY_STOR_CO as total stores, although this CSV's
    legacy Korean field reads 'similar-industry stores'. Never add it again to
    general or franchise stores.
    """
    needed = {QUARTER, DONG, NAME, SECTOR, TOTAL, "점포_수", "프랜차이즈_점포_수"}
    if not needed <= set(stores):
        raise ValueError("Incomplete official store schema")
    data = stores.copy()
    data[DONG] = integer_ids(data[DONG])
    data = data[data[DONG].str.startswith("11440")].copy()
    expected = {
        str(code): value.removeprefix("서울특별시 마포구 ")
        for code, value in names.items()
        if value.startswith("서울특별시 마포구 ")
    }
    if len(expected) != 16 or len(set(expected.values())) != 16:
        raise ValueError("Require 16 unique official Mapo names")
    if set(data[QUARTER]) != {20241, 20242, 20243, 20244}:
        raise ValueError("Require all four 2024 quarters and no other year")
    if (
        data[list(needed)].isna().any().any()
        or data.duplicated([QUARTER, DONG, SECTOR]).any()
    ):
        raise ValueError("Duplicate or missing quarter/dong/industry records")
    pairs = data[[DONG, NAME]].drop_duplicates()
    if (
        len(pairs) != 16
        or pairs[DONG].duplicated().any()
        or pairs[NAME].duplicated().any()
    ):
        raise ValueError("Ambiguous commercial administrative codes")
    if set(pairs[NAME]) != set(expected.values()):
        raise ValueError("Mapo administrative names disagree with provider lookup")
    numeric = [TOTAL, "점포_수", "프랜차이즈_점포_수"]
    data[numeric] = finite_nonnegative(data, numeric, integer=True)
    if not data[TOTAL].eq(data["점포_수"] + data["프랜차이즈_점포_수"]).all():
        raise ValueError("Total must equal general plus franchise stores")
    inverse = {name: code for code, name in expected.items()}
    pairs = pairs.rename(columns={DONG: "seoul_dong_id", NAME: "name"})
    pairs["grid_id"] = pairs.name.map(inverse)
    totals = data.groupby([DONG, QUARTER])[TOTAL].sum().unstack(QUARTER)
    if totals.shape != (16, 4) or totals.isna().any().any():
        raise ValueError("Incomplete dong/quarter support; no zero filling")
    totals.columns = [f"stores_{q}" for q in totals.columns]
    totals["stores_mean"] = totals.mean(axis=1)
    coverage = (
        data.groupby([DONG, QUARTER])
        .agg(
            reported_industries=(SECTOR, "nunique"),
            reported_total_stores=(TOTAL, "sum"),
        )
        .reset_index()
    )
    features = pairs.merge(
        totals, left_on="seoul_dong_id", right_index=True, validate="one_to_one"
    )
    return features.sort_values("grid_id").reset_index(drop=True), coverage


def provider_road_aggregates(roads, network, metadata, expected_network_sha256):
    """Length-weighted available-link context on the provider's nominal dongs."""
    required_roads = {
        "link_id",
        "length_km",
        "road_class",
        "all_vehicles_per_day",
        "trucks_per_day",
    }
    required_network = {"k_link_id", "emd_id", "sigungu_id", "k_length"}
    if (
        not required_roads <= set(roads)
        or not required_network <= set(network)
        or roads.empty
    ):
        raise ValueError(
            "Require a nonempty complete road context and provider network schema"
        )
    if metadata.get("year") != 2024 or metadata.get("day_type") != "평일":
        raise ValueError("Require 2024 provider weekday road context")
    if metadata.get("statistic") != "annual_average_day":
        raise ValueError("Require annual averages, not copied daily samples")
    if (
        not isinstance(expected_network_sha256, str)
        or not expected_network_sha256
        or metadata.get("network", {}).get("network_sha256") != expected_network_sha256
    ):
        raise ValueError("Network checksum mismatch")
    source = network.copy()
    for key in ["k_link_id", "emd_id", "sigungu_id"]:
        source[key] = integer_ids(source[key])
    source[["k_length"]] = finite_nonnegative(source, ["k_length"])
    if source.k_link_id.duplicated().any():
        raise ValueError("Duplicate network link IDs")
    data = roads.copy()
    data["link_id"] = integer_ids(data.link_id)
    if data.link_id.duplicated().any():
        raise ValueError("Duplicate traffic link IDs")
    if data.road_class.isna().any():
        raise ValueError("Missing road classification")
    fields = ["length_km", "all_vehicles_per_day", "trucks_per_day"]
    data[fields] = finite_nonnegative(data, fields)
    data = data.merge(
        source[["k_link_id", "emd_id", "sigungu_id", "k_length"]],
        left_on="link_id",
        right_on="k_link_id",
        how="left",
        validate="one_to_one",
    )
    if data.emd_id.isna().any() or not data.sigungu_id.eq("11140").all():
        raise ValueError("Unmatched or non-Mapo network attribution")
    if (data.length_km <= 0).any() or not np.allclose(
        data.length_km, data.k_length, atol=1e-6, rtol=0
    ):
        raise ValueError("Provider lengths disagree or are nonpositive")
    rows = []
    for grid, group in data.groupby("emd_id"):
        row = {"grid_id": grid}
        for scope in ["all", "local"]:
            subset = (
                group
                if scope == "all"
                else group[
                    ~group.road_class.isin(
                        ["고속도로", "도시고속도로", "고속도로_연결로"]
                    )
                ]
            )
            row[f"links_{scope}"] = len(subset)
            row[f"length_km_{scope}"] = float(subset.length_km.sum())
            for kind, column in [
                ("all", "all_vehicles_per_day"),
                ("truck", "trucks_per_day"),
            ]:
                row[f"traffic_{kind}_{scope}"] = (
                    float(np.average(subset[column], weights=subset.length_km))
                    if len(subset)
                    else np.nan
                )
        rows.append(row)
    return pd.DataFrame(rows).sort_values("grid_id"), data


def build_candidate_features(
    stores, names, roads, network, metadata, expected_network_sha256
):
    stocks, store_coverage = mapo_stores(stores, names)
    road_features, link_map = provider_road_aggregates(
        roads, network, metadata, expected_network_sha256
    )
    if set(road_features.grid_id) - set(stocks.grid_id):
        raise ValueError(
            "Road provider dong is absent from reviewed commercial crosswalk"
        )
    coverage = stocks.merge(
        road_features, on="grid_id", how="left", validate="one_to_one"
    )
    required = [c for c in road_features if c.startswith("traffic_")]
    coverage["eligible"] = coverage[required].notna().all(axis=1)
    coverage["reason"] = np.where(
        coverage.eligible,
        "complete_reported_context",
        "no_complete_reported_road_context_not_zero",
    )
    eligible = coverage[coverage.eligible].sort_values("grid_id").reset_index(drop=True)
    return eligible, coverage, store_coverage, link_map


def _eligible_sales(sales, features):
    needed = {QUARTER, DONG, NAME, SECTOR, "당월_매출_건수"}
    if not needed <= set(sales):
        raise ValueError("Incomplete official transaction schema")
    if not {"grid_id", "seoul_dong_id", "name"} <= set(features):
        raise ValueError("Missing locked candidate identifiers")
    if features[["grid_id", "seoul_dong_id", "name"]].isna().any().any() or any(
        features[column].duplicated().any()
        for column in ["grid_id", "seoul_dong_id", "name"]
    ):
        raise ValueError("Locked candidate identifiers must be unique and present")
    data = sales.copy()
    data[DONG] = integer_ids(data[DONG])
    data = data[data[DONG].str.startswith("11440")].copy()
    if set(data[QUARTER]) != {20251, 20252, 20253, 20254}:
        raise ValueError("Require all four 2025 quarters and no other year")
    if (
        data[list(needed)].isna().any().any()
        or data.duplicated([QUARTER, DONG, SECTOR]).any()
    ):
        raise ValueError("Duplicate or missing outcome quarter/dong/industry")
    if data[SECTOR].astype(str).str.strip().eq("").any():
        raise ValueError("Missing reported outcome industry")
    data[["당월_매출_건수"]] = finite_nonnegative(
        data, ["당월_매출_건수"], integer=True
    )
    names = features.set_index("seoul_dong_id")["name"]
    subset = data[data[DONG].isin(names.index)].copy()
    if not subset[NAME].eq(subset[DONG].map(names)).all():
        raise ValueError("Outcome dong names disagree with locked input")
    coverage = (
        subset.groupby([DONG, QUARTER])
        .size()
        .unstack(QUARTER)
        .reindex(features.seoul_dong_id)
    )
    if coverage.shape != (len(features), 4) or coverage.isna().any().any():
        raise ValueError("Missing outcome dong/quarter; no zero filling")
    return subset


def common_reported_sectors(sales, features):
    """Coverage-only intersection; absent industry rows are never imputed as zero."""
    subset = _eligible_sales(sales, features)
    groups = subset.groupby([DONG, QUARTER])[SECTOR].agg(set)
    return sorted(set.intersection(*groups))


def _selected_indices(selected, n):
    chosen = np.asarray(selected)
    if (
        chosen.ndim != 1
        or not len(chosen)
        or chosen.dtype.kind not in "iu"
        or (chosen < 0).any()
        or (chosen >= n).any()
        or len(set(chosen)) != len(chosen)
    ):
        raise ValueError("Selection must contain unique in-range integer indices")
    return chosen.astype(int)


def evaluate_public_outcomes(sales, features, scores, selections):
    """Retrospective association with estimated transactions, not ad outcomes.

    Candidate order is the locked features order. Shares use the same eligible
    dong population as their denominator. K is required to be equal across
    comparisons. A set-only decision such as minimax gets no invented ranking.
    """
    subset = _eligible_sales(sales, features)
    selected_sets = {
        name: _selected_indices(chosen, len(features))
        for name, chosen in selections.items()
    }
    if (
        not selected_sets
        or len({len(chosen) for chosen in selected_sets.values()}) != 1
    ):
        raise ValueError("Require nonempty same-K model selections")
    if set(scores) - set(selected_sets):
        raise ValueError("Score model is absent from selected-set comparison")
    vectors = {}
    for name, score in scores.items():
        vector = np.asarray(score, dtype=float)
        if (
            vector.ndim != 1
            or len(vector) != len(features)
            or not np.isfinite(vector).all()
        ):
            raise ValueError("Outcome comparison requires finite aligned score vectors")
        vectors[name] = vector
    records, values = [], []
    for quarter, group in subset.groupby(QUARTER):
        y = group.groupby(DONG)["당월_매출_건수"].sum().reindex(features.seoul_dong_id)
        if y.isna().any() or y.sum() <= 0:
            raise ValueError("Missing outcome or zero eligible total; share undefined")
        industries = (
            group.groupby(DONG)[SECTOR].nunique().reindex(features.seoul_dong_id)
        )
        target = y.to_numpy(dtype=float)
        for model, chosen in selected_sets.items():
            record = {
                "quarter": int(quarter),
                "primary": quarter == 20251,
                "model": model,
                "k": len(chosen),
                "eligible_dongs": len(features),
                "selected_transaction_share": float(
                    target[chosen].sum() / target.sum()
                ),
                "target": "reported_estimated_card_transactions_not_advertising_outcomes",
            }
            if model in vectors:
                vector = vectors[model]
                rho = (
                    spearmanr(vector, target).statistic
                    if np.ptp(vector) and np.ptp(target)
                    else np.nan
                )
                deleted = [
                    spearmanr(np.delete(vector, i), np.delete(target, i)).statistic
                    for i in range(len(target))
                    if np.ptp(np.delete(vector, i)) and np.ptp(np.delete(target, i))
                ]
                record.update(
                    spearman=rho,
                    leave_one_dong_out_min=min(deleted) if deleted else np.nan,
                    leave_one_dong_out_max=max(deleted) if deleted else np.nan,
                )
            records.append(record)
        for grid, name, value, count in zip(
            features.grid_id, features["name"], target, industries, strict=True
        ):
            values.append(
                {
                    "grid_id": grid,
                    "name": name,
                    "quarter": int(quarter),
                    "reported_transactions": value,
                    "reported_industries": int(count),
                }
            )
    return pd.DataFrame(records), pd.DataFrame(values)
