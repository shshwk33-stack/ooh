"""View-T population aggregates: requested periods, not independent GPS or people."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

COLUMNS = [
    "origin_id",
    "destination_id",
    "period_trips",
    "mean_daily_trips",
    "origin_latitude",
    "origin_longitude",
    "destination_latitude",
    "destination_longitude",
]


def requested_dates(request):
    """Reconstruct the explicit Detail query; never infer coverage from a response."""
    day_term = str(request["dayTerm"])
    if "/" in day_term:
        first, last = [
            datetime.strptime(x, "%Y%m%d").date() for x in day_term.split("/")
        ]
        if last < first or (last - first).days > 366:
            raise ValueError("Invalid requested date interval")
        dates = [first + timedelta(days=i) for i in range((last - first).days + 1)]
    else:
        dates = [datetime.strptime(x, "%Y%m%d").date() for x in day_term.split(",")]
    if not dates or len(dates) != len(set(dates)) or dates != sorted(dates):
        raise ValueError("Missing, repeated or unsorted dates")
    if len(dates) != int(request["daysCnt"]) or any(
        d.year != int(request["year"]) for d in dates
    ):
        raise ValueError("Requested day count / year mismatch")
    return dates


def _values(rows):
    if not isinstance(rows, list) or not rows:
        raise ValueError("No returned population rows; missing is not zero")
    frame = pd.DataFrame(rows)
    if not {"zone", "V", "SX", "SY", "EX", "EY"}.issubset(frame):
        raise ValueError("Unexpected population response columns")
    if not frame.zone.map(
        lambda x: isinstance(x, str) and re.fullmatch(r"\d{8}-\d{8}", x) is not None
    ).all():
        raise ValueError("Unexpected provider O/D identifier")
    if frame.zone.duplicated().any():
        raise ValueError("Repeated O/D pairs")
    for column in ["V", "SX", "SY", "EX", "EY"]:
        if frame[column].map(lambda x: isinstance(x, bool)).any():
            raise ValueError("Boolean population value")
        frame[column] = pd.to_numeric(frame[column], errors="raise")
        if not np.isfinite(frame[column]).all():
            raise ValueError("Missing / non-finite population value")
    if frame.V.lt(0).any():
        raise ValueError("Negative population / suppressed sentinel")
    # The official response uses X for LATITUDE and Y for LONGITUDE.
    for column in ["SX", "EX"]:
        if not frame[column].between(32, 40).all():
            raise ValueError("Unexpected Korean latitude; verify axis order")
    for column in ["SY", "EY"]:
        if not frame[column].between(124, 132).all():
            raise ValueError("Unexpected Korean longitude; verify axis order")
    return frame.set_index("zone").sort_index()


def _pair(total_rows, average_rows, days):
    total, average = _values(total_rows), _values(average_rows)
    if not total.index.equals(average.index):
        raise ValueError("Total and average O/D coverage differ")
    if not np.allclose(
        total[["SX", "SY", "EX", "EY"]],
        average[["SX", "SY", "EX", "EY"]],
        rtol=0,
        atol=1e-9,
    ):
        raise ValueError("O/D coordinates differ between metrics")
    if not np.allclose(total.V / days, average.V, rtol=0, atol=0.00051):
        raise ValueError("Period total / requested days differs from provider average")
    pairs = total.index.str.split("-", expand=True)
    result = pd.DataFrame(
        {
            "origin_id": pairs.get_level_values(0),
            "destination_id": pairs.get_level_values(1),
            "period_trips": total.V.to_numpy(),
            "mean_daily_trips": average.V.to_numpy(),
            "origin_latitude": total.SX.to_numpy(),
            "origin_longitude": total.SY.to_numpy(),
            "destination_latitude": total.EX.to_numpy(),
            "destination_longitude": total.EY.to_numpy(),
        }
    )
    result["internal_same_zone"] = result.origin_id.eq(result.destination_id)
    return result


def normalize_response(payload, request, kind):
    """Preserve distinct totals and averages; never add density / reciprocal totals."""
    dates = requested_dates(request)
    blocks = payload.get("all") if isinstance(payload, dict) else None
    if not isinstance(blocks, list) or not blocks:
        raise ValueError("Empty / rejected population response")
    selected = str(request["zone"]).split(",")
    if len(selected) != len(set(selected)):
        raise ValueError("Duplicate selected destinations")
    if kind == "inflow":
        if request.get("trafficType") != "In" or str(request.get("subZoneType")) != "0":
            raise ValueError("This adapter supports nationwide-origin inflow only")
        if len(blocks) != len(selected):
            raise ValueError("Selected destinations and response blocks differ")
        frames = []
        for block, destination in zip(blocks, selected, strict=True):
            if not isinstance(block, list) or len(block) != 3:
                raise ValueError("Expected total, average and density blocks")
            frame = _pair(block[0], block[1], len(dates))
            if not frame.destination_id.eq(destination).all():
                raise ValueError("Returned destination differs from query")
            # Density is preserved in the raw response, never mixed into flow.
            frames.append(frame)
        table = pd.concat(frames, ignore_index=True)
    elif kind == "od":
        if len(blocks) != 9 or request.get("LineType") != "OOD":
            raise ValueError("Expected directed OOD response contract")
        table = _pair(blocks[1], blocks[5], len(dates))
        if len(table) >= int(request["drawlimits"]):
            raise ValueError("O/D result reaches provider cap; completeness is unknown")
        if table.internal_same_zone.any():
            raise ValueError("Unexpected self-pair in directed inter-zone O/D")
    else:
        raise ValueError("Expected inflow or od")
    if table.duplicated(["origin_id", "destination_id"]).any():
        raise ValueError("Duplicate O/D keys after combining response blocks")
    metadata = {
        "source": "KTDB View-T Expert response format; authentication is recorded separately",
        "source_url": "https://viewt.ktdb.go.kr/cong/map/second_map.do",
        "kind": kind,
        "year": int(request["year"]),
        "observation_type": "estimated",
        "origin_unit": {"2": "sigungu", "3": "dong"}.get(
            str(request["displayResult"]), "unsupported"
        ),
        "destination_unit": {"2": "sigungu", "3": "dong"}.get(
            str(request["zoneType"] if kind == "inflow" else request["displayResult"]),
            "unsupported",
        ),
        "requested_start": str(dates[0]),
        "requested_end": str(dates[-1]),
        "requested_days": len(dates),
        "requested_dates": [str(d) for d in dates],
        "coverage": "returned_rows_only; underlying daily coverage not independently certified",
        "statistic": "requested_period_total_and_provider_mean",
        "total_unit": "person_trips_over_requested_period",
        "average_unit": "person_trips_per_requested_day",
        "timezone": "Asia/Seoul",
        "coordinates": "provider representative points; SX/EX latitude, SY/EY longitude",
        "request": request,
        "rows": len(table),
        "limitations": [
            "Not unique people, pedestrian counts or advertising impressions.",
            "No missing O/D row is converted into zero.",
            "An aggregated response is not a collection of daily samples.",
            "Population inflow and O/D tools overlap; do not add their totals.",
        ],
    }
    if "unsupported" in [metadata["origin_unit"], metadata["destination_unit"]]:
        raise ValueError("Unsupported spatial unit")
    if metadata["origin_unit"] != metadata["destination_unit"]:
        # A sigungu code cannot be compared with a dong code as if they were peers.
        table["internal_same_zone"] = pd.Series(
            pd.NA, index=table.index, dtype="boolean"
        )
    return table, metadata


def read_download(path, kind):
    path = Path(path)
    raw = path.read_bytes()
    request_path = path.with_suffix(".request.json")
    request = json.loads(request_path.read_text())
    table, metadata = normalize_response(json.loads(raw), request, kind)
    metadata.update(
        raw_sha256=hashlib.sha256(raw).hexdigest(),
        request_sha256=hashlib.sha256(request_path.read_bytes()).hexdigest(),
    )
    return table, metadata


def export_population(raw_directory, output):
    """Export acquired files only. All destinations must have matching query conditions."""
    raw_directory, output = Path(raw_directory), Path(output)
    coverage_file = raw_directory / "daily_coverage.json"
    coverage = (
        json.loads(coverage_file.read_text()) if coverage_file.is_file() else None
    )
    name_path = raw_directory / "zone_names_2024.json"
    names = json.loads(name_path.read_text())["shpMap"]
    files = [
        p
        for p in sorted(raw_directory.glob("mapo_*inflow_*.json"))
        if not p.name.endswith(".request.json")
    ]
    datasets = []
    for path in files:
        table, meta = read_download(path, "inflow")
        if (
            coverage
            and meta["requested_days"] == 1
            and meta["destination_unit"] == "dong"
            and meta["requested_start"] in coverage["missing_dates"]
        ):
            continue
        datasets.append((path.stem, table, meta))
    for path in sorted(raw_directory.glob("mapo_od_*.json")):
        if not path.name.endswith(".request.json"):
            table, meta = read_download(path, "od")
            datasets.append((path.stem, table, meta))
    if not datasets:
        raise ValueError("No acquired population files")
    manifest = {
        "schema": "viewt_population_context_v1",
        "names_year": 2024,
        "name_source_sha256": hashlib.sha256(name_path.read_bytes()).hexdigest(),
        "datasets": [],
    }
    if coverage is not None:
        manifest["daily_coverage"] = coverage
        manifest["daily_coverage_sha256"] = hashlib.sha256(
            coverage_file.read_bytes()
        ).hexdigest()
    prepared = []
    for name, frame, meta in datasets:
        if meta["year"] != 2024:
            raise ValueError("Name lookup year does not match request")
        for side in ["origin", "destination"]:
            frame[side + "_name"] = frame[side + "_id"].map(names)
            if frame[side + "_name"].isna().any():
                raise ValueError("Unresolved official zone name")
        frame["within_mapo"] = frame.origin_name.str.fullmatch(
            r"서울특별시 마포구(?: .+)?"
        ) & frame.destination_name.str.fullmatch(r"서울특별시 마포구(?: .+)?")
        csv = frame.to_csv(index=False).encode("utf-8-sig")
        prepared.append((name, csv))
        manifest["datasets"].append(
            {
                "name": name,
                "metadata": meta,
                "csv_sha256": hashlib.sha256(csv).hexdigest(),
            }
        )
    output.mkdir(parents=True, exist_ok=True)
    for name, csv in prepared:
        (output / (name + ".csv")).write_bytes(csv)
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2)
    )
    return manifest


def load_population(directory):
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text())
    if manifest.get("schema") != "viewt_population_context_v1":
        raise ValueError("Unexpected population manifest")
    result = []
    for item in manifest["datasets"]:
        path = directory / (item["name"] + ".csv")
        if path.resolve().parent != directory.resolve():
            raise ValueError("Invalid dataset path")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != item["csv_sha256"]:
            raise ValueError("Population CSV checksum mismatch")
        frame = pd.read_csv(path, dtype={"origin_id": str, "destination_id": str})
        if len(frame) != item["metadata"]["rows"]:
            raise ValueError("Population row count mismatch")
        result.append((item["name"], frame, item["metadata"]))
    return result


def combine_inflow_batches(datasets):
    """Join different destinations only when every other query condition matches."""
    if not datasets:
        raise ValueError("No inflow batches")
    requests = []
    destinations = set()
    for _, frame, meta in datasets:
        if meta["kind"] != "inflow":
            raise ValueError("Only inflow batches can be combined")
        request = dict(meta["request"])
        declared = set(str(request.pop("zone")).split(","))
        if declared != set(frame.destination_id) or destinations & declared:
            raise ValueError("Missing or overlapping batch destinations")
        destinations |= declared
        requests.append(request)
    if any(r != requests[0] for r in requests[1:]):
        raise ValueError("Incompatible population query conditions")
    return pd.concat([frame for _, frame, _ in datasets], ignore_index=True)


def aggregation_check(district, dongs):
    """Cross-query consistency, not independent accuracy or effectiveness validation."""
    if district.destination_id.nunique() != 1:
        raise ValueError("Expected one aggregate destination")
    left = district.groupby("origin_id").period_trips.sum()
    right = dongs.groupby("origin_id").period_trips.sum()
    if set(left.index) != set(right.index):
        raise ValueError("District/dong origins differ; do not fill missing rows")
    return {
        "origin_count": len(left),
        "destination_dong_count": dongs.destination_id.nunique(),
        "district_total": float(left.sum()),
        "dong_total": float(right.sum()),
        "max_origin_difference": float((left - right.reindex(left.index)).abs().max()),
        "interpretation": "same-source aggregation consistency; not independent validation",
    }


def daily_inflow_panel(datasets, expected_destinations):
    """Keep actual single-date queries; annual/weekly averages never become days."""
    by_date = {}
    reference = None
    for item in datasets:
        meta = item[2]
        if (
            meta["kind"] != "inflow"
            or meta["destination_unit"] != "dong"
            or meta["requested_days"] != 1
        ):
            continue
        condition = {
            k: v for k, v in meta["request"].items() if k not in ["zone", "dayTerm"]
        }
        if reference is None:
            reference = condition
        elif condition != reference:
            raise ValueError("Daily sample query conditions differ")
        by_date.setdefault(meta["requested_start"], []).append(item)
    frames = []
    for day, items in sorted(by_date.items()):
        frame = combine_inflow_batches(items)
        if set(frame.destination_id) != set(expected_destinations):
            raise ValueError("Incomplete destination coverage on a sampled date")
        daily = frame.groupby("destination_id", as_index=False).agg(
            reported_trips=("period_trips", "sum")
        )
        daily["date"] = day
        frames.append(daily)
    if not frames:
        raise ValueError("No actual single-date dong queries")
    return pd.concat(frames, ignore_index=True)


def population_rank_stability(panel, *, cluster="day", n=1000, seed=42):
    """Paired day/week resampling of reported flows; no accuracy/effectiveness claim."""
    if cluster not in {"day", "week"} or n < 20:
        raise ValueError("Choose day/week and at least 20 replicates")
    if panel.duplicated(["date", "destination_id"]).any():
        raise ValueError("Repeated daily candidate sample")
    matrix = (
        panel.pivot(index="date", columns="destination_id", values="reported_trips")
        .sort_index()
        .sort_index(axis=1)
    )
    if (
        len(matrix) < 5
        or matrix.shape[1] < 10
        or not np.isfinite(matrix.to_numpy()).all()
        or (matrix < 0).any().any()
    ):
        raise ValueError(
            "Need complete nonnegative samples, >=5 dates and >=10 candidates"
        )
    dates = pd.to_datetime(matrix.index)
    groups = [[i] for i in range(len(matrix))]
    if cluster == "week":
        weeks = dates.to_period("W-SUN")
        groups = [np.flatnonzero(weeks == week).tolist() for week in sorted(set(weeks))]
    if len(groups) < 2:
        raise ValueError("Need at least two resampling units")
    values = matrix.to_numpy()
    rng = np.random.default_rng(seed)
    scores, ranks, draws = [], [], []
    selected5 = np.zeros(values.shape[1])
    selected10 = np.zeros(values.shape[1])
    for replicate in range(n):
        sampled = rng.integers(0, len(groups), len(groups))
        positions = [i for group in sampled for i in groups[group]]
        means = values[positions].mean(axis=0)
        order = np.argsort(-means, kind="stable")  # Ties: provider ID ascending.
        selected5[order[:5]] += 1
        selected10[order[:10]] += 1
        scores.append(means)
        ranks.append(
            pd.Series(means).rank(ascending=False, method="average").to_numpy()
        )
        draws.append(
            {
                "method": cluster,
                "replicate": replicate,
                "drawn_units": json.dumps(sampled.tolist()),
                "drawn_dates": json.dumps(matrix.index[positions].tolist()),
                "unique_dates": len(set(positions)),
            }
        )
    scores = np.array(scores)
    ranks = np.array(ranks)
    result = pd.DataFrame(
        {
            "destination_id": matrix.columns,
            "mean_reported_trips": values.mean(axis=0),
            "mean_p025": np.quantile(scores, 0.025, axis=0),
            "mean_p975": np.quantile(scores, 0.975, axis=0),
            "rank_p025": np.quantile(ranks, 0.025, axis=0),
            "rank_p975": np.quantile(ranks, 0.975, axis=0),
            "top5_probability": selected5 / n,
            "top10_probability": selected10 / n,
            "method": cluster,
            "sample_days": len(matrix),
            "resampling_units": len(groups),
            "replicates": n,
            "seed": seed,
        }
    )
    return result, pd.DataFrame(draws)
