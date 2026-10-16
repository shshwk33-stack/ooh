"""Same-network road context for representative paths, not a GPS mobility model."""

from __future__ import annotations

import numpy as np
import pandas as pd
from pyproj import Geod
from shapely.geometry import shape


def summarize_route_context(routes, geometry, route_metadata, roads):
    """Length-weighted traffic and sum(length / annual mean speed).

    The latter is a plug-in scenario, NOT mean observed journey time. Missing
    links and zero speed make the entire route metric unavailable. Components
    cannot be summed across legs to claim a connected, drivable milk-run.
    """
    rm, cm = route_metadata, roads.metadata
    if (
        rm.get("year") != cm.get("year")
        or cm.get("statistic") != "annual_average_day"
        or cm.get("day_type") != "평일"
        or cm.get("network_level") != "5.5"
        or not rm.get("sources")
    ):
        raise ValueError(
            "Require same year, annual weekday road context and route requests"
        )
    network = rm.get("network", {}).get("network_sha256")
    if not network or network != cm.get("network", {}).get("network_sha256"):
        raise ValueError("Same road network checksum required")
    for source in rm["sources"]:
        req = source["request"]
        if (
            req.get("YEAR") != cm["year"]
            or req.get("WEEKTYPE") != 0
            or req.get("TIME") != "ALL"
        ):
            raise ValueError("Route period differs from weekday/all-day road context")
    geod, geom = Geod(ellps="WGS84"), {}
    for feature in geometry["features"]:
        key = str(feature["properties"]["link_id"])
        g = shape(feature["geometry"])
        if g.geom_type != "LineString" or not g.is_valid or g.is_empty:
            raise ValueError("Valid individual LineStrings required")
        if key in geom and not geom[key].equals_exact(g, 1e-10):
            raise ValueError("Conflicting geometry for the same link")
        if not (
            124 <= g.bounds[0] <= g.bounds[2] <= 132
            and 33 <= g.bounds[1] <= g.bounds[3] <= 39
        ):
            raise ValueError("Geometry must be Korea longitude/latitude EPSG:4326")
        geom[key] = g
    table = roads.table.copy()
    if table.link_id.duplicated().any():
        raise ValueError("Unique road context link IDs required")
    for col in ["all_vehicles_per_day", "speed_kmh"]:
        if not np.isfinite(table[col]).all() or (table[col] < 0).any():
            raise ValueError("Nonnegative finite road values required")
    links = table.set_index("link_id")
    geometry_checks = {(r["leg"], r["rank"]): r for r in rm["summaries"]}
    records = []
    for (leg, rank), group in routes.groupby(["leg", "rank"], sort=True):
        group = group.sort_values("sequence")
        if group.sequence.tolist() != list(range(len(group))):
            raise ValueError("Route order is incomplete")
        if not set(group.link_id) <= geom.keys():
            raise ValueError("Incomplete route geometry")
        lengths = np.array(
            [geod.geometry_length(geom[k]) / 1000 for k in group.link_id]
        )
        if not np.isfinite(lengths).all() or (lengths <= 0).any():
            raise ValueError("Positive geodesic link lengths required")
        matched = group.link_id.isin(links.index).to_numpy()
        complete = bool(matched.all())
        traffic = speed = np.nan
        status = "missing_road_context"
        if complete:
            context = links.loc[group.link_id]
            traffic = float(np.average(context.all_vehicles_per_day, weights=lengths))
            status = "zero_speed_time_unavailable"
            if (context.speed_kmh > 0).all():
                speed = float(np.sum(lengths / context.speed_kmh.to_numpy() * 60))
                status = "complete_context"
        check = geometry_checks[(leg, rank)]
        records.append(
            {
                "leg": leg,
                "rank": int(rank),
                "share_percent": float(group.share_percent.iloc[0]),
                "links": len(group),
                "matched_links": int(matched.sum()),
                "geometry_length_km": float(lengths.sum()),
                "context_length_coverage": float(
                    lengths[matched].sum() / lengths.sum()
                ),
                "length_weighted_traffic_per_day": traffic,
                "link_time_proxy_minutes": speed,
                "max_nearest_endpoint_gap_m": check["max_nearest_endpoint_gap_m"],
                "gaps_over_10m": check["gaps_over_10m"],
                "missing_link_ids": ";".join(
                    sorted(set(group.loc[~matched, "link_id"]))
                ),
                "status": status,
                "drivability": "unverified",
                "basis": "provider_paths_plus_annual_road_context_derived_scenario",
            }
        )
    return pd.DataFrame(records)
