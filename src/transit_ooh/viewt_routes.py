"""Provider representative vehicle paths; percentages never become vehicle counts."""

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Geod

from .viewt_roads import RoadContext, attach_network


def normalize_routes(payload, request):
    if (
        payload.get("STATE") != 200
        or not isinstance(payload.get("RESULT"), list)
        or not payload["RESULT"]
    ):
        raise ValueError("No valid vehicle path response")
    for field in ["DPRTR_ZONEID", "ARRIVE_ZONEID"]:
        if str(payload[field]) != str(request[field]):
            raise ValueError("Returned O/D differs from query")
    routes = payload["RESULT"]
    if payload["CNT"] != len(routes) or len(routes) > 5:
        raise ValueError("Unexpected route count")
    ranks, shares, records = [], [], []
    for route in routes:
        rank, share = route["RANK"], route["VALUE"]
        if isinstance(rank, bool) or not isinstance(rank, int) or not 1 <= rank <= 5:
            raise ValueError("Invalid route rank")
        if (
            isinstance(share, bool)
            or not isinstance(share, (int, float))
            or not np.isfinite(share)
            or not 0 <= share <= 100
        ):
            raise ValueError("Invalid route percentage")
        ranks.append(rank)
        shares.append(share)
        links = route.get(
            "LINKS"
        )  # Actual endpoint schema differs from older LINKIDS documentation.
        if not isinstance(links, list) or not links or route["CNT"] != len(links):
            raise ValueError("Unexpected route link count")
        orders = [link["ORDER"] for link in links]
        if any(isinstance(x, bool) or not isinstance(x, int) for x in orders) or sorted(
            orders
        ) != list(range(len(links))):
            raise ValueError("Missing or duplicate path sequence")
        for link in sorted(links, key=lambda x: x["ORDER"]):
            identifier = link["LINKID"]
            if (
                isinstance(identifier, bool)
                or not isinstance(identifier, int)
                or identifier < 0
            ):
                raise ValueError("Invalid route link ID")
            records.append(
                {
                    "origin_id": str(request["DPRTR_ZONEID"]),
                    "destination_id": str(request["ARRIVE_ZONEID"]),
                    "rank": rank,
                    "share_percent": float(share),
                    "sequence": link["ORDER"],
                    "link_id": str(identifier),
                    "road_name": link.get("LINKNAME"),
                    "provider_length_km": link.get("LINKLENGTH"),
                    "year": int(request["YEAR"]),
                    "route_basis": "provider_representative_path",
                }
            )
    if len(ranks) != len(set(ranks)) or sum(shares) > 100.01:
        raise ValueError("Duplicate route ranks or invalid percentage sum")
    return pd.DataFrame(records)


def export_routes(raw_directory, network, output):
    raw_directory, output = Path(raw_directory), Path(output)
    tables, sources = [], []
    for file in sorted(raw_directory.glob("vehicle_paths_*.json")):
        if file.name.endswith(".request.json"):
            continue
        raw = file.read_bytes()
        reqfile = file.with_suffix(".request.json")
        request = json.loads(reqfile.read_text())
        table = normalize_routes(json.loads(raw), request)
        if (
            request["YEAR"] != 2024
            or request["WEEKTYPE"] != 0
            or request["TIME"] != "ALL"
        ):
            raise ValueError("This export expects 2024 weekday all-day paths")
        table["leg"] = (
            str(request["DPRTR_ZONEID"]) + "_" + str(request["ARRIVE_ZONEID"])
        )
        tables.append(table)
        sources.append(
            {
                "file": file.name,
                "request": request,
                "raw_sha256": hashlib.sha256(raw).hexdigest(),
                "request_sha256": hashlib.sha256(reqfile.read_bytes()).hexdigest(),
            }
        )
    if not tables:
        raise ValueError("No vehicle path files")
    frame = pd.concat(tables, ignore_index=True)
    if frame.duplicated(["leg", "rank", "sequence"]).any():
        raise ValueError("Repeated route source")
    unique = pd.DataFrame({"link_id": sorted(frame.link_id.unique())})
    geometry, netmeta = attach_network(
        RoadContext(unique, {"year": 2024}), network, 2024
    )
    shapes = {f["properties"]["link_id"]: f["geometry"] for f in geometry["features"]}
    features = []
    geod = Geod(ellps="WGS84")
    summaries = []
    for (leg, rank), group in frame.groupby(["leg", "rank"], sort=True):
        ordered = group.sort_values("sequence")
        gaps = []
        previous = None
        for row in ordered.to_dict("records"):
            g = shapes[row["link_id"]]
            lines = (
                [g["coordinates"]] if g["type"] == "LineString" else g["coordinates"]
            )
            endpoints = [p for line in lines for p in [line[0], line[-1]]]
            if previous:
                gaps.append(
                    min(
                        abs(geod.inv(a[0], a[1], b[0], b[1])[2])
                        for a in previous
                        for b in endpoints
                    )
                )
            previous = endpoints
            features.append({"type": "Feature", "properties": row, "geometry": g})
        summaries.append(
            {
                "leg": leg,
                "rank": int(rank),
                "share_percent": float(ordered.share_percent.iloc[0]),
                "links": len(ordered),
                "max_nearest_endpoint_gap_m": max(gaps, default=0),
                "gaps_over_10m": sum(g > 10 for g in gaps),
            }
        )
    metadata = {
        "schema": "viewt_vehicle_paths_v1",
        "year": 2024,
        "sources": sources,
        "network": netmeta,
        "route_count": len(summaries),
        "leg_count": frame.leg.nunique(),
        "unique_links": len(unique),
        "summaries": summaries,
        "limitations": [
            "Representative routes are not continuous delivery GPS.",
            "Usage percentages are not vehicle counts or shipment probabilities.",
            "Endpoint proximity does not validate direction, turns, delivery access or connections between legs.",
            "Three selected O/D legs illustrate a hypothetical cycle, not a verified driveable milk-run.",
        ],
    }
    output.mkdir(parents=True, exist_ok=True)
    for name, data in [
        ("routes.csv", frame.to_csv(index=False).encode("utf-8-sig")),
        (
            "routes.geojson",
            json.dumps(
                {"type": "FeatureCollection", "features": features},
                ensure_ascii=False,
                allow_nan=False,
            ).encode(),
        ),
    ]:
        (output / name).write_bytes(data)
        metadata[name + "_sha256"] = hashlib.sha256(data).hexdigest()
    (output / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2)
    )
    return metadata


def load_routes(directory):
    directory = Path(directory)
    metadata = json.loads((directory / "metadata.json").read_text())
    if metadata.get("schema") != "viewt_vehicle_paths_v1":
        raise ValueError("Invalid route metadata")
    for name in ["routes.csv", "routes.geojson"]:
        if (
            hashlib.sha256((directory / name).read_bytes()).hexdigest()
            != metadata[name + "_sha256"]
        ):
            raise ValueError("Route artifact checksum mismatch")
    frame = pd.read_csv(
        directory / "routes.csv",
        dtype={"origin_id": str, "destination_id": str, "link_id": str},
    )
    geometry = json.loads((directory / "routes.geojson").read_text())
    return frame, geometry, metadata
