"""Strict local-file adapter for aggregate transport exports; not an official API.

This schema belongs to Transit OOH. Provider exports require an explicit mapping.
No aggregate path is accepted as a continuous vehicle GPS observation.
"""

from __future__ import annotations

import heapq
import itertools
import json
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Geod

from .decision import specification_audit, weight_audit
from .scoring import MinMax, rank_metrics, top_keys

# Approximate map starting positions, NOT administrative boundaries or study sites.
DISTRICTS = {
    "마포구": ("11440", 37.5638, 126.9084),
    "종로구": ("11110", 37.5730, 126.9794),
    "중구": ("11140", 37.5641, 126.9979),
    "용산구": ("11170", 37.5326, 126.9905),
    "성동구": ("11200", 37.5633, 127.0369),
    "광진구": ("11215", 37.5385, 127.0823),
    "동대문구": ("11230", 37.5744, 127.0396),
    "중랑구": ("11260", 37.6063, 127.0928),
    "성북구": ("11290", 37.5894, 127.0167),
    "강북구": ("11305", 37.6396, 127.0257),
    "도봉구": ("11320", 37.6688, 127.0471),
    "노원구": ("11350", 37.6542, 127.0568),
    "은평구": ("11380", 37.6028, 126.9292),
    "서대문구": ("11410", 37.5791, 126.9368),
    "양천구": ("11470", 37.5170, 126.8665),
    "강서구": ("11500", 37.5509, 126.8495),
    "구로구": ("11530", 37.4955, 126.8874),
    "금천구": ("11545", 37.4569, 126.8955),
    "영등포구": ("11560", 37.5264, 126.8963),
    "동작구": ("11590", 37.5124, 126.9393),
    "관악구": ("11620", 37.4784, 126.9515),
    "서초구": ("11650", 37.4837, 127.0324),
    "강남구": ("11680", 37.5172, 127.0473),
    "송파구": ("11710", 37.5146, 127.1056),
    "강동구": ("11740", 37.5301, 127.1238),
}
TYPES = {"public_observed", "estimated", "synthetic"}
UNITS = {
    "population_segments": "person_trips",
    "population_od": "person_trips",
    "vehicle_paths": "vehicle_trips",
    "poi": "poi_count",
}
REQUIRED = {
    "candidates": ["zone_id", "name", "district_code", "longitude", "latitude"],
    "population_segments": ["zone_id", "date", "hour", "population_flow"],
    "population_od": ["origin_id", "destination_id", "date", "hour", "population_flow"],
    "vehicle_paths": [
        "route_id",
        "zone_id",
        "sequence",
        "date",
        "hour",
        "vehicle_flow",
    ],
    "poi": ["zone_id", "poi_count"],
}


@dataclass
class Bundle:
    tables: dict[str, pd.DataFrame]
    metadata: dict

    @property
    def observation_type(self):
        kinds = {v["observation_type"] for v in self.metadata["components"].values()}
        return (
            "synthetic"
            if kinds == {"synthetic"}
            else (
                "public_observed"
                if kinds == {"public_observed"}
                else "mixed_observed_estimated"
            )
        )


def read_bundle(path_or_bytes) -> Bundle:
    """Read one XLSX (metadata key/value JSON sheet) or CSV directory + metadata.json."""
    if isinstance(path_or_bytes, (bytes, bytearray)):
        sheets = pd.read_excel(BytesIO(path_or_bytes), sheet_name=None, dtype=object)
        meta = json.loads(str(sheets.pop("metadata").iloc[0]["json"]))
    else:
        path = Path(path_or_bytes)
        if path.is_dir():
            meta = json.loads((path / "metadata.json").read_text(encoding="utf-8"))
            sheets = {
                p.stem: pd.read_csv(p, dtype=object, encoding="utf-8-sig")
                for p in path.glob("*.csv")
            }
        else:
            return read_bundle(path.read_bytes())
    return validate_bundle(Bundle(sheets, meta))


def workbook(bundle: Bundle) -> bytes:
    buff = BytesIO()
    with pd.ExcelWriter(buff, engine="openpyxl") as writer:
        pd.DataFrame(
            {"json": [json.dumps(bundle.metadata, ensure_ascii=False)]}
        ).to_excel(writer, sheet_name="metadata", index=False)
        for name, frame in bundle.tables.items():
            frame.to_excel(writer, sheet_name=name, index=False)
    return buff.getvalue()


def _numeric(d, column, *, integer=False, lower=0, upper=None):
    d[column] = pd.to_numeric(d[column], errors="raise")
    v = d[column]
    if (
        not np.isfinite(v).all()
        or (v < lower).any()
        or (upper is not None and (v > upper).any())
        or (integer and (v % 1 != 0).any())
    ):
        raise ValueError(f"Invalid numeric field: {column}")
    if integer:
        d[column] = v.astype(int)


def validate_bundle(bundle: Bundle) -> Bundle:
    tables = {k: v.copy() for k, v in bundle.tables.items()}
    meta = json.loads(json.dumps(bundle.metadata))
    required_meta = {
        "schema_version",
        "district_code",
        "spatial_support_id",
        "spatial_unit",
        "timezone",
        "year",
        "start_date",
        "end_date",
        "hours",
        "population_basis",
        "components",
    }
    if missing := required_meta - meta.keys():
        raise ValueError(f"Missing metadata: {sorted(missing)}")
    if (
        meta["schema_version"] != "transit-ooh-viewt-1"
        or meta["timezone"] != "Asia/Seoul"
    ):
        raise ValueError("Require schema transit-ooh-viewt-1 and Asia/Seoul timezone")
    if not meta["spatial_support_id"] or not meta["spatial_unit"]:
        raise ValueError("Explicit spatial support / zone version required")
    district = str(meta["district_code"])
    if district not in {v[0] for v in DISTRICTS.values()}:
        raise ValueError("Select one Seoul district code")
    meta["district_code"] = district
    start, end = pd.Timestamp(meta["start_date"]), pd.Timestamp(meta["end_date"])
    if (
        start.tzinfo is not None
        or end.tzinfo is not None
        or start != start.normalize()
        or end != end.normalize()
        or end < start
        or start.year != int(meta["year"])
        or end.year != int(meta["year"])
    ):
        raise ValueError("Require one matching calendar year and valid local dates")
    hours = meta["hours"]
    if (
        not hours
        or len(set(hours)) != len(hours)
        or any(not isinstance(h, int) or not 0 <= h <= 23 for h in hours)
    ):
        raise ValueError("hours must be unique local integers 0..23")
    basis = meta["population_basis"]
    if basis not in {"segments", "od_destination"}:
        raise ValueError(
            "population_basis must be segments or od_destination (never their sum)"
        )
    population_table = "population_segments" if basis == "segments" else "population_od"
    if not {"candidates", "poi", "vehicle_paths", population_table} <= tables.keys():
        raise ValueError(
            "Require candidates, poi, vehicle_paths and selected population table"
        )
    if set(tables) - REQUIRED.keys():
        raise ValueError(f"Unknown sheets: {set(tables) - REQUIRED.keys()}")
    if set(meta["components"]) != set(tables) - {"candidates"}:
        raise ValueError("Every input component needs its own metadata")
    kinds = set()
    expected_pairs = {
        (str(d.date()), h) for d in pd.date_range(start, end) for h in hours
    }
    for name, d in tables.items():
        if d.columns.duplicated().any():
            raise ValueError(f"{name}: duplicate column names")
        if missing := set(REQUIRED[name]) - set(d.columns):
            raise ValueError(
                f"{name}: missing columns {sorted(missing)}; map provider columns explicitly"
            )
        if d.empty or d[REQUIRED[name]].isna().any().any():
            raise ValueError(f"{name}: empty / missing required values")
        for col in (
            "zone_id",
            "origin_id",
            "destination_id",
            "route_id",
            "district_code",
        ):
            if col in d:
                d[col] = d[col].astype(str).str.strip()
                if (d[col] == "").any():
                    raise ValueError(f"{name}: empty identifier")
        if name == "candidates":
            continue
        c = meta["components"][name]
        required_component = {
            "source",
            "source_url",
            "observation_type",
            "unit",
            "year",
            "timezone",
            "spatial_support_id",
            "spatial_unit",
            "start_date",
            "end_date",
            "coverage",
        }
        if required_component - c.keys():
            raise ValueError(f"{name}: incomplete source/period/unit metadata")
        for field in (
            "year",
            "timezone",
            "spatial_support_id",
            "spatial_unit",
            "start_date",
            "end_date",
        ):
            if c[field] != meta[field]:
                raise ValueError(f"{name}: incompatible {field}; no automatic joining")
        if (
            c["observation_type"] not in TYPES
            or c["unit"] != UNITS[name]
            or not c["source"]
            or not c["source_url"]
        ):
            raise ValueError(f"{name}: invalid provenance or unit")
        if c["coverage"] != "complete_with_structural_zeros":
            raise ValueError(
                f"{name}: declare complete coverage; unknown missingness cannot become zero"
            )
        if (
            "observation_type" not in d
            or not (d.observation_type == c["observation_type"]).all()
        ):
            raise ValueError(f"{name}: row observation_type must match metadata")
        kinds.add(c["observation_type"])
        if name == "poi":
            _numeric(d, "poi_count")
            if d.zone_id.duplicated().any():
                raise ValueError("Duplicate POI zone")
            if (
                "valid_from" not in c
                or "valid_to" not in c
                or pd.Timestamp(c["valid_from"]) > start
                or pd.Timestamp(c["valid_to"]) < end
            ):
                raise ValueError(
                    "POI validity must explicitly cover the analysis period"
                )
        else:
            if c.get("statistic") != "period_total" or c.get("hours") != hours:
                raise ValueError(
                    f"{name}: require matching hours and period_total (not average-day estimates)"
                )
            _numeric(d, "hour", integer=True, upper=23)
            dates = pd.to_datetime(d.date, format="%Y-%m-%d", errors="raise")
            if (dates != dates.dt.normalize()).any() or dates.dt.tz is not None:
                raise ValueError("Dates must be local calendar dates")
            d["date"] = dates.dt.strftime("%Y-%m-%d")
            pairs = set(zip(d.date, d.hour, strict=False))
            if pairs != expected_pairs:
                raise ValueError(f"{name}: missing / extra date-hour coverage")
            _numeric(
                d, "vehicle_flow" if name == "vehicle_paths" else "population_flow"
            )
            keys = ["date", "hour"] + (
                {
                    "vehicle_paths": ["route_id", "sequence"],
                    "population_segments": ["zone_id"],
                    "population_od": ["origin_id", "destination_id"],
                }[name]
            )
            if d.duplicated(keys).any():
                raise ValueError(f"{name}: duplicate analytical key")
            if name == "vehicle_paths":
                _numeric(d, "sequence", integer=True)
                if (
                    d.groupby(["route_id", "date", "hour"]).vehicle_flow.nunique() > 1
                ).any():
                    raise ValueError(
                        "One route-date-hour must carry a single flow value"
                    )
                if c.get("path_semantics") not in {
                    "representative_zone_sequence",
                    "estimated_zone_sequence",
                }:
                    raise ValueError(
                        "Declare aggregate path semantics; vehicle GPS is unsupported here"
                    )
    if "synthetic" in kinds and kinds != {"synthetic"}:
        raise ValueError("Do not mix synthetic and actual/estimated source components")
    cand = tables["candidates"]
    if cand.zone_id.duplicated().any() or set(cand.district_code) != {district}:
        raise ValueError("Unique candidates in the selected district required")
    _numeric(cand, "longitude", lower=124, upper=132)
    _numeric(cand, "latitude", lower=33, upper=39)
    zones = set(cand.zone_id)
    if set(tables["poi"].zone_id) != zones:
        raise ValueError(
            "POI coverage must match candidates exactly; missing is not zero"
        )
    for name, d in tables.items():
        for col in ("zone_id", "destination_id"):
            if col in d and not set(d[col]) <= zones:
                raise ValueError(
                    f"{name}: unmapped {col}; provide a reviewed spatial crosswalk first"
                )
    # OD origins outside the district are allowed: only destination attraction is used.
    if "population_segments" in tables:
        p = tables["population_segments"]
        if len(p) != len(expected_pairs) * len(zones):
            raise ValueError(
                "population_segments requires explicit zone × date × hour coverage"
            )
    return Bundle(tables, meta)


def demo_bundle(district="마포구", days=14, seed=42) -> Bundle:
    """A fully synthetic, district-centred scenario; no View-T observations."""
    code, lat, lon = DISTRICTS[district]
    rng = np.random.default_rng(seed)
    ids = [f"DEMO-{code}-{i:02}" for i in range(16)]
    candidates = pd.DataFrame(
        [
            {
                "zone_id": key,
                "name": f"가상 거점 {i + 1:02}",
                "district_code": code,
                "longitude": lon + (i % 4 - 1.5) * 0.006,
                "latitude": lat + (i // 4 - 1.5) * 0.0045,
            }
            for i, key in enumerate(ids)
        ]
    )
    dates = pd.date_range("2025-10-01", periods=days)
    hours = [8, 9, 10, 12, 14, 16, 18]
    population, paths, od = [], [], []
    pop_base, traffic_base = rng.uniform(300, 2200, 16), rng.uniform(20, 100, 4)
    routes = [
        [*list(range(16)), 0],
        [*list(range(15, -1, -1)), 15],
        [0, 5, 10, 15, 0],
        [3, 6, 9, 12, 3],
    ]
    for day in dates:
        shock = rng.lognormal(0, 0.3, 16)
        for hour in hours:
            for i, key in enumerate(ids):
                flow = round(
                    pop_base[i]
                    * shock[i]
                    * rng.lognormal(0, 0.25)
                    * (1.4 if hour in [8, 18] else 1)
                )
                population.append([key, str(day.date()), hour, flow, "synthetic"])
                od.append(
                    [ids[(i + 5) % 16], key, str(day.date()), hour, flow, "synthetic"]
                )
            for r, seq in enumerate(routes):
                flow = round(traffic_base[r] * rng.lognormal(0, 0.6))
                for order, i in enumerate(seq):
                    paths.append(
                        [
                            f"DEMO-R{r}",
                            ids[i],
                            order,
                            str(day.date()),
                            hour,
                            flow,
                            "synthetic",
                        ]
                    )
    tables = {
        "candidates": candidates,
        "population_segments": pd.DataFrame(
            population,
            columns=["zone_id", "date", "hour", "population_flow", "observation_type"],
        ),
        "population_od": pd.DataFrame(
            od,
            columns=[
                "origin_id",
                "destination_id",
                "date",
                "hour",
                "population_flow",
                "observation_type",
            ],
        ),
        "vehicle_paths": pd.DataFrame(
            paths,
            columns=[
                "route_id",
                "zone_id",
                "sequence",
                "date",
                "hour",
                "vehicle_flow",
                "observation_type",
            ],
        ),
        "poi": pd.DataFrame(
            {
                "zone_id": ids,
                "poi_count": rng.integers(5, 180, 16),
                "observation_type": "synthetic",
            }
        ),
    }
    meta = {
        "schema_version": "transit-ooh-viewt-1",
        "district_code": code,
        "spatial_support_id": f"DEMO-{code}-v1",
        "spatial_unit": "synthetic_candidate_zone",
        "timezone": "Asia/Seoul",
        "year": 2025,
        "start_date": str(dates[0].date()),
        "end_date": str(dates[-1].date()),
        "hours": hours,
        "population_basis": "segments",
        "components": {},
        "seed": seed,
        "boundary_note": "Approximate district-centred demonstration; not official administrative boundaries",
    }
    for name, unit in UNITS.items():
        meta["components"][name] = {
            k: meta[k]
            for k in [
                "year",
                "timezone",
                "spatial_support_id",
                "spatial_unit",
                "start_date",
                "end_date",
            ]
        }
        meta["components"][name].update(
            source="Transit OOH synthetic generator; NOT View-T",
            source_url="synthetic://transit-ooh/viewt-demo-v1",
            observation_type="synthetic",
            unit=unit,
            coverage="complete_with_structural_zeros",
            statistic="period_total",
            hours=hours,
        )
    meta["components"]["poi"].update(
        valid_from=meta["start_date"], valid_to=meta["end_date"]
    )
    meta["components"]["vehicle_paths"]["path_semantics"] = "estimated_zone_sequence"
    return validate_bundle(Bundle(tables, meta))


def daily_features(bundle, hours=None, dates=None):
    hours = bundle.metadata["hours"] if hours is None else list(hours)
    dates = (
        sorted(bundle.tables["vehicle_paths"].date.unique())
        if dates is None
        else list(dates)
    )
    if (
        not hours
        or not dates
        or not set(hours) <= set(bundle.metadata["hours"])
        or not set(dates) <= set(bundle.tables["vehicle_paths"].date)
    ):
        raise ValueError("Select covered hours and dates")

    def selected(name):
        d = bundle.tables[name]
        return d[d.hour.isin(hours) & d.date.isin(dates)].copy()

    if bundle.metadata["population_basis"] == "segments":
        pop = selected("population_segments")
    else:
        pop = selected("population_od").rename(columns={"destination_id": "zone_id"})
    pop = pop.groupby(["date", "zone_id"]).population_flow.sum()
    # A route traversing a zone twice is counted once in route-zone trip incidence.
    vehicles = selected("vehicle_paths").drop_duplicates(
        ["route_id", "date", "hour", "zone_id"]
    )
    traffic = vehicles.groupby(["date", "zone_id"]).vehicle_flow.sum()
    index = pd.MultiIndex.from_product(
        [dates, bundle.tables["candidates"].zone_id], names=["date", "zone_id"]
    )
    return pd.DataFrame(
        {
            "population": pop.reindex(index, fill_value=0),
            "vehicle_flow": traffic.reindex(index, fill_value=0),
        }
    ).reset_index()


def aggregate_days(bundle, daily, draws=None):
    if draws is not None:
        daily = pd.concat([daily[daily.date == d] for d in draws], ignore_index=True)
    f = daily.groupby("zone_id", as_index=False)[["population", "vehicle_flow"]].mean()
    f = f.merge(
        bundle.tables["poi"][["zone_id", "poi_count"]],
        validate="one_to_one",
        on="zone_id",
    )
    f = f.merge(bundle.tables["candidates"], validate="one_to_one", on="zone_id")
    return f.rename(columns={"zone_id": "grid_id"})


def score_aggregate(features, alpha=0.5, normalizer=None, population_weight=0.7):
    if not 0 <= alpha <= 1 or not 0 <= population_weight <= 1:
        raise ValueError("Weights must be within [0,1]")
    norm = normalizer or MinMax().fit(
        features, ["population", "poi_count", "vehicle_flow"]
    )
    z = norm.transform(features)
    d = features.copy()
    d["static_score"] = (
        population_weight * z.population + (1 - population_weight) * z.poi_count
    )
    d["mobility_score"] = z.vehicle_flow
    d["integrated_score"] = alpha * d.mobility_score + (1 - alpha) * d.static_score
    for name in ["static", "mobility", "integrated"]:
        d[name + "_rank"] = d[name + "_score"].rank(ascending=False, method="average")
    d["mobility_weight"] = alpha
    d["population_weight_within_spatial"] = population_weight
    d["score_type"] = "assumed_decision_index"
    d["mobility_basis"] = "aggregate_vehicle_trip_incidence_NOT_GPS_dwell_or_visits"
    return d, norm


def analyze_bundle(
    bundle,
    alpha=0.5,
    hours=None,
    dates=None,
    bootstrap_n=100,
    seed=42,
    population_weight=0.7,
    bootstrap_unit="day",
):
    if not isinstance(bootstrap_n, int) or bootstrap_n < 0:
        raise ValueError("bootstrap_n must be a nonnegative integer")
    bundle = validate_bundle(bundle)
    if bootstrap_unit not in {"day", "week"}:
        raise ValueError("Bootstrap unit must be day or week")
    daily = daily_features(bundle, hours, dates)
    features = aggregate_days(bundle, daily)
    scores, norm = score_aggregate(features, alpha, population_weight=population_weight)
    scores["input_observation_type"] = bundle.observation_type
    sensitivity, ranks, comparisons = [], [], []
    for weight in sorted(set(np.round(np.linspace(0, 1, 21), 8)) | {float(alpha), 0.6}):
        s, _ = score_aggregate(features, weight, norm, population_weight)
        for k in [5, 10]:
            sensitivity.append(
                {
                    "mobility_weight": weight,
                    "is_reference": bool(np.isclose(weight, alpha)),
                    **rank_metrics(scores, s, k=k),
                }
            )
        ranks.extend(
            s[
                ["grid_id", "integrated_rank", "integrated_score", "mobility_weight"]
            ].to_dict("records")
        )
    for a, b in [
        ("static", "mobility"),
        ("static", "integrated"),
        ("mobility", "integrated"),
    ]:
        for k in [5, 10]:
            comparisons.append(
                {
                    "model_a": a,
                    "model_b": b,
                    **rank_metrics(scores, scores, a + "_score", b + "_score", k),
                }
            )
    days = sorted(daily.date.unique())
    blocks = {}
    for day in days:
        key = (
            day
            if bootstrap_unit == "day"
            else str(pd.Timestamp(day).to_period("W-SUN"))
        )
        blocks.setdefault(key, []).append(day)
    reps, drawscores, selection = (
        [],
        [],
        {k: {z: 0 for z in scores.grid_id} for k in [5, 10]},
    )
    if len(blocks) >= 3 and bootstrap_n > 0:
        rng = np.random.default_rng(seed)
        for rep in range(bootstrap_n):
            chosen = rng.choice(sorted(blocks), len(blocks), replace=True)
            draws = [day for key in chosen for day in blocks[key]]
            s, _ = score_aggregate(
                aggregate_days(bundle, daily, draws), alpha, norm, population_weight
            )
            drawscores.append(s.set_index("grid_id").integrated_score)
            for k in [5, 10]:
                for z in top_keys(s, k=k):
                    selection[k][z] += 1
            reps.append(
                {
                    "replicate": rep,
                    "drawn_days": ";".join(draws),
                    "unique_days": len(set(draws)),
                    "drawn_blocks": ";".join(chosen),
                    "block_count": len(blocks),
                    "resampling_unit": bootstrap_unit,
                    **rank_metrics(scores, s, k=5),
                    "mobility_spearman": rank_metrics(
                        scores, s, "mobility_score", "mobility_score"
                    )["spearman"],
                }
            )
    stability = []
    if drawscores:
        samples = pd.DataFrame(drawscores)
        for z in scores.grid_id:
            stability.append(
                {
                    "grid_id": z,
                    "top5_probability": selection[5][z] / bootstrap_n,
                    "top10_probability": selection[10][z] / bootstrap_n,
                    "score_p025": samples[z].quantile(0.025),
                    "score_p975": samples[z].quantile(0.975),
                    "replicates": bootstrap_n,
                    "day_clusters": len(days),
                    "block_count": len(blocks),
                    "resampling_unit": f"paired_whole_{bootstrap_unit}_with_replacement",
                    "interval_scope": "conditional_stability_not_advertising_accuracy",
                }
            )
    holdout = []
    if len(days) >= 4:
        train, test = days[: len(days) // 2], days[len(days) // 2 :]
        a, fitted = score_aggregate(
            aggregate_days(bundle, daily[daily.date.isin(train)]),
            alpha,
            population_weight=population_weight,
        )
        b, _ = score_aggregate(
            aggregate_days(bundle, daily[daily.date.isin(test)]),
            alpha,
            fitted,
            population_weight,
        )
        for model in ["static", "mobility", "integrated"]:
            holdout.append(
                {
                    "model": model,
                    "train_days": len(train),
                    "test_days": len(test),
                    "normalization": "train_only_frozen",
                    **rank_metrics(a, b, model + "_score", model + "_score"),
                    "interpretation": "temporal_rank_stability_NOT_independent_outcome_accuracy",
                }
            )
    rankframe = pd.DataFrame(ranks)
    acceptability = (
        rankframe.assign(in_top5=rankframe.integrated_rank <= 5)
        .groupby("grid_id", as_index=False)
        .agg(
            best_rank=("integrated_rank", "min"), worst_rank=("integrated_rank", "max")
        )
    )
    return {
        "scores": scores,
        "daily": daily,
        "model_comparison": pd.DataFrame(comparisons),
        "weight_sensitivity": pd.DataFrame(sensitivity),
        "weight_ranks": rankframe,
        "weight_rank_range": acceptability,
        "bootstrap_replicates": pd.DataFrame(reps),
        "selection_stability": pd.DataFrame(stability),
        "temporal_holdout": pd.DataFrame(holdout),
        **weight_audit(scores),
        **specification_audit(features, alpha, population_weight),
    }


def milk_run(bundle, hubs, hours=None, cycles=2, speed_kmh=20, dwell_minutes=5):
    """Directed route on aggregate zone adjacency, NOT a navigable road route.

    Travel times use a declared constant speed and geodesic centroid distances.
    Connectivity comes only from supplied path sequences; no gap-filling edges.
    """
    if (
        len(hubs) < 2
        or len(set(hubs)) != len(hubs)
        or cycles < 1
        or speed_kmh <= 0
        or dwell_minutes < 0
    ):
        raise ValueError(
            "Require distinct hubs, positive cycles/speed and nonnegative dwell"
        )
    candidates = bundle.tables["candidates"].set_index("zone_id")
    if not set(hubs) <= set(candidates.index):
        raise ValueError("Unknown milk-run hub")
    paths = bundle.tables["vehicle_paths"]
    if hours is not None:
        paths = paths[paths.hour.isin(hours)]
    adjacency = {z: {} for z in candidates.index}
    geod = Geod(ellps="WGS84")
    for _, g in paths.groupby(["route_id", "date", "hour"]):
        seq = g.sort_values("sequence").zone_id.tolist()
        for a, b in itertools.pairwise(seq):
            if a == b:
                continue
            pa, pb = candidates.loc[a], candidates.loc[b]
            distance = float(
                geod.inv(pa.longitude, pa.latitude, pb.longitude, pb.latitude)[2]
            )
            adjacency[a][b] = distance

    def shortest(start, end):
        queue = [(0.0, start, [start])]
        visited = set()
        while queue:
            cost, node, path = heapq.heappop(queue)
            if node == end:
                return path
            if node in visited:
                continue
            visited.add(node)
            for nxt, dist in adjacency[node].items():
                if nxt not in visited:
                    heapq.heappush(queue, (cost + dist, nxt, [*path, nxt]))
        raise ValueError(
            f"Disconnected supplied path network: {start} → {end}; no invented connector"
        )

    rows, elapsed, order = [], 0.0, 0
    obs = "synthetic" if bundle.observation_type == "synthetic" else "estimated"
    for cycle in range(cycles):
        for a, b in zip(hubs, hubs[1:] + hubs[:1], strict=False):
            seq = shortest(a, b)
            for z, nxt in itertools.pairwise(seq):
                pa, pb = candidates.loc[z], candidates.loc[nxt]
                duration = adjacency[z][nxt] / (speed_kmh / 3.6)
                rows.append(
                    {
                        "cycle": cycle + 1,
                        "sequence": order,
                        "from_zone": z,
                        "to_zone": nxt,
                        "path": [
                            [pa.longitude, pa.latitude],
                            [pb.longitude, pb.latitude],
                        ],
                        "start_seconds": elapsed,
                        "travel_seconds": duration,
                        "assumed_dwell_seconds": dwell_minutes * 60 if nxt == b else 0,
                        "observation_type": obs,
                        "geometry_semantics": "schematic_zone_centroid_chords_NOT_road_geometry",
                        "speed_kmh_assumption": speed_kmh,
                    }
                )
                elapsed += duration + (dwell_minutes * 60 if nxt == b else 0)
                order += 1
    return pd.DataFrame(rows)
