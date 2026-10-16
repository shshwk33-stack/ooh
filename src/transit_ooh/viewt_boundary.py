"""Year-specific provider map boundaries for display, not precise road allocation."""

import hashlib
import json
from pathlib import Path

from pyproj import Transformer
from shapely import transform, union_all
from shapely.geometry import Point, shape


def prepare_mapo_boundary(payload, names):
    if (
        payload.get("type") != "FeatureCollection"
        or payload.get("numberReturned") != len(payload["features"])
        or payload.get("numberMatched") != len(payload["features"])
    ):
        raise ValueError("Incomplete provider geometry response")
    if payload.get("crs", {}).get("properties", {}).get("name") not in {
        "urn:ogc:def:crs:EPSG::4326",
        "EPSG:4326",
    }:
        raise ValueError("Explicit EPSG:4326 boundary response required")
    expected = {
        str(k): v
        for k, v in names["shpMap"].items()
        if v.startswith("서울특별시 마포구 ")
    }
    if len(expected) != 16:
        raise ValueError("Expected 16 official Mapo dong names for 2024")
    features = [
        f
        for f in payload["features"]
        if f["properties"]["full_name"].startswith("서울특별시 마포구 ")
    ]
    actual = {
        str(f["properties"]["zone_id"]): f["properties"]["full_name"] for f in features
    }
    if len(features) != 16 or actual != expected:
        raise ValueError("Boundary codes/names differ from population lookup")
    metric = Transformer.from_crs(4326, 5179, always_xy=True).transform
    polygons, checks, output = [], [], []
    for feature in features:
        p, g = feature["properties"], shape(feature["geometry"])
        if (
            g.geom_type not in {"Polygon", "MultiPolygon"}
            or not g.is_valid
            or g.is_empty
        ):
            raise ValueError("Valid polygon boundary required")
        if not (
            126 < g.bounds[0] < g.bounds[2] < 128
            and 37 < g.bounds[1] < g.bounds[3] < 38
        ):
            raise ValueError("Boundary coordinate order/range invalid")
        if not g.covers(Point(p["lon"], p["lat"])):
            raise ValueError("Official label location falls outside its polygon")
        projected = transform(g, metric, interleaved=False)
        polygons.append(projected)
        area = float(p["areavalue"])
        if not area > 0:
            raise ValueError("Positive provider area required")
        difference = abs(projected.area / area - 1)
        checks.append(
            {
                "zone_id": str(p["zone_id"]),
                "name": p["name"],
                "geometry_area_m2": projected.area,
                "provider_area_m2": area,
                "relative_area_difference": difference,
            }
        )
        output.append(
            {
                "type": "Feature",
                "properties": {
                    "zone_id": str(p["zone_id"]),
                    "name": p["name"],
                    "full_name": p["full_name"],
                    "year": 2024,
                },
                "geometry": feature["geometry"],
            }
        )
    overlap = sum(g.area for g in polygons) - union_all(polygons).area
    if overlap > 1:
        raise ValueError("Mapo polygon interiors overlap by more than one square metre")
    return {"type": "FeatureCollection", "features": output}, {
        "schema": "viewt_map_boundary_v1",
        "year": 2024,
        "district": "마포구",
        "layer": "sqlite:zone_emd_2024",
        "crs": "EPSG:4326",
        "rows": 16,
        "codes_and_full_names_match_population": True,
        "overlap_area_m2": max(0.0, overlap),
        "geometry_checks": checks,
        "use": "choropleth_display_only",
        "precision": "web_map_geometry_not_verified_for_precise_link_allocation",
        "max_relative_area_difference": max(
            c["relative_area_difference"] for c in checks
        ),
    }


def export_boundary(payload, names, provenance, directory):
    geo, metadata = prepare_mapo_boundary(payload, names)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(geo, ensure_ascii=False, allow_nan=False).encode()
    (directory / "mapo_2024.geojson").write_bytes(raw)
    metadata.update(
        provenance=provenance, geometry_sha256=hashlib.sha256(raw).hexdigest()
    )
    (directory / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2)
    )
    return metadata


def load_boundary(directory):
    directory = Path(directory)
    meta = json.loads((directory / "metadata.json").read_text())
    raw = (directory / "mapo_2024.geojson").read_bytes()
    if (
        meta.get("schema") != "viewt_map_boundary_v1"
        or meta.get("year") != 2024
        or hashlib.sha256(raw).hexdigest() != meta.get("geometry_sha256")
    ):
        raise ValueError("Invalid boundary year or checksum")
    return json.loads(raw), meta


def choropleth(geo, points, year):
    """Exact provider code/name join; never nearest-coordinate guessing."""
    if year != 2024 or points.destination_id.duplicated().any():
        raise ValueError("Require unique 2024 population destinations")
    keys = {f["properties"]["zone_id"] for f in geo["features"]}
    if set(points.destination_id) != keys:
        raise ValueError("Population/boundary coverage differs")
    features = []
    table = points.set_index("destination_id")
    maximum = float(points.daily_mean.max())
    for feature in geo["features"]:
        p = dict(feature["properties"])
        row = table.loc[p["zone_id"]]
        if row.destination_name != p["full_name"]:
            raise ValueError("Population/boundary name differs")
        value = float(row.daily_mean)
        if not 0 <= value <= maximum:
            raise ValueError("Invalid population mean")
        strength = value / maximum if maximum else 0.0
        p.update(
            daily_mean=round(value, 1),
            color=[
                int(221 - 200 * strength),
                int(239 - 110 * strength),
                int(246 - 90 * strength),
                190,
            ],
        )
        features.append(
            {"type": "Feature", "properties": p, "geometry": feature["geometry"]}
        )
    return {"type": "FeatureCollection", "features": features}
