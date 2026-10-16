"""Small synthetic geometry fixtures test joins and missingness, not field effects."""

import copy
import json

import numpy as np
import pandas as pd
import pytest
from shapely.geometry import box, mapping

from transit_ooh.route_context import summarize_route_context
from transit_ooh.viewt_boundary import (
    choropleth,
    export_boundary,
    load_boundary,
    prepare_mapo_boundary,
)
from transit_ooh.viewt_roads import RoadContext


@pytest.fixture
def route_fixture():
    routes = pd.DataFrame(
        {
            "leg": ["X_Y", "X_Y"],
            "rank": [1, 1],
            "sequence": [0, 1],
            "link_id": ["01", "02"],
            "share_percent": [50.0, 50.0],
        }
    )
    geometry = {
        "features": [
            {
                "properties": {"link_id": "01"},
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[126.9, 37.55], [126.91, 37.55]],
                },
            },
            {
                "properties": {"link_id": "02"},
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[126.91, 37.55], [126.92, 37.55]],
                },
            },
        ]
    }
    meta = {
        "year": 2024,
        "network": {"network_sha256": "0" * 64},
        "sources": [{"request": {"YEAR": 2024, "WEEKTYPE": 0, "TIME": "ALL"}}],
        "summaries": [
            {
                "leg": "X_Y",
                "rank": 1,
                "max_nearest_endpoint_gap_m": 0,
                "gaps_over_10m": 0,
            }
        ],
    }
    roads = RoadContext(
        pd.DataFrame(
            {
                "link_id": ["01", "02"],
                "all_vehicles_per_day": [100.0, 200.0],
                "speed_kmh": [10.0, 20.0],
            }
        ),
        {
            "year": 2024,
            "statistic": "annual_average_day",
            "day_type": "평일",
            "network_level": "5.5",
            "network": {"network_sha256": "0" * 64},
        },
    )
    return routes, geometry, meta, roads


def test_length_weighting_and_missing_road_never_zero_fill(route_fixture):
    routes, geo, meta, roads = route_fixture
    row = summarize_route_context(*route_fixture).iloc[0]
    assert row.length_weighted_traffic_per_day == pytest.approx(150, rel=1e-6)
    assert row.link_time_proxy_minutes == pytest.approx(
        row.geometry_length_km / 2 * (1 / 10 + 1 / 20) * 60
    )
    roads.table = roads.table.head(1)
    missing = summarize_route_context(routes, geo, meta, roads).iloc[0]
    assert missing.context_length_coverage == pytest.approx(0.5)
    assert missing.missing_link_ids == "02"
    assert np.isnan(missing.link_time_proxy_minutes)
    assert np.isnan(missing.length_weighted_traffic_per_day)


def test_network_year_zero_speed_and_geometry_conflicts(route_fixture):
    _routes, geo, _meta, roads = route_fixture
    roads.table.loc[0, "speed_kmh"] = 0
    row = summarize_route_context(*route_fixture).iloc[0]
    assert np.isnan(row.link_time_proxy_minutes) and np.isfinite(
        row.length_weighted_traffic_per_day
    )
    roads.metadata["year"] = 2025
    with pytest.raises(ValueError, match="same year"):
        summarize_route_context(*route_fixture)
    roads.metadata["year"] = 2024
    geo["features"].append(copy.deepcopy(geo["features"][0]))
    geo["features"][-1]["geometry"]["coordinates"][0][0] += 0.01
    with pytest.raises(ValueError, match="Conflicting"):
        summarize_route_context(*route_fixture)


@pytest.fixture
def boundary_fixture():
    names, features = {}, []
    for i in range(16):
        zone, name = str(10000000 + i), f"서울특별시 마포구 TEST{i}동"
        x, y = 126.9 + (i % 4) * 0.002, 37.55 + (i // 4) * 0.002
        names[zone] = name
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "zone_id": int(zone),
                    "full_name": name,
                    "name": f"TEST{i}동",
                    "lon": x + 0.0005,
                    "lat": y + 0.0005,
                    "areavalue": 10000,
                },
                "geometry": mapping(box(x, y, x + 0.001, y + 0.001)),
            }
        )
    return {
        "type": "FeatureCollection",
        "numberReturned": 16,
        "numberMatched": 16,
        "crs": {"properties": {"name": "EPSG:4326"}},
        "features": features,
    }, {"shpMap": names}


def test_boundary_year_names_codes_hash_and_zero_population(boundary_fixture, tmp_path):
    payload, names = boundary_fixture
    geo, meta = prepare_mapo_boundary(payload, names)
    assert meta["rows"] == 16 and meta["use"] == "choropleth_display_only"
    export_boundary(payload, names, {"fixture": True}, tmp_path)
    restored, _ = load_boundary(tmp_path)
    assert restored == json.loads(json.dumps(geo))
    points = pd.DataFrame(
        {
            "destination_id": list(names["shpMap"]),
            "destination_name": list(names["shpMap"].values()),
            "daily_mean": [0.0] * 16,
        }
    )
    assert len(choropleth(geo, points, 2024)["features"]) == 16
    with pytest.raises(ValueError, match="2024"):
        choropleth(geo, points, 2023)
    points.loc[0, "destination_name"] = "WRONG"
    with pytest.raises(ValueError, match="name"):
        choropleth(geo, points, 2024)
    (tmp_path / "mapo_2024.geojson").write_text("{}")
    with pytest.raises(ValueError, match="checksum"):
        load_boundary(tmp_path)


def test_truncated_or_overlapping_geometry_rejected(boundary_fixture):
    payload, names = boundary_fixture
    payload["numberMatched"] = 17
    with pytest.raises(ValueError, match="Incomplete"):
        prepare_mapo_boundary(payload, names)
    payload["numberMatched"] = 16
    payload["features"][1]["geometry"] = payload["features"][0]["geometry"]
    payload["features"][1]["properties"]["lon"] = payload["features"][0]["properties"][
        "lon"
    ]
    with pytest.raises(ValueError, match="overlap"):
        prepare_mapo_boundary(payload, names)
