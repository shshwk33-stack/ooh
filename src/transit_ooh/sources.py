"""Bounded, verified public downloads and source-specific non-GPS adapters."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import requests

from .io import provenance, sha256, write_json


class SourceError(RuntimeError):
    pass


def download(url, path, max_bytes=50_000_000, expected_sha256=None, session=None):
    """TLS stays enabled. Partial/failed downloads are never labelled observed data."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and expected_sha256 and sha256(path) == expected_sha256:
        sidecar = Path(str(path) + ".provenance.json")
        result = json.loads(sidecar.read_text()) if sidecar.exists() else {}
        result.update(
            url=url,
            path=str(path),
            sha256=expected_sha256,
            bytes=path.stat().st_size,
            status="verified_cache",
        )
        return result
    part = path.with_suffix(path.suffix + ".part")
    client = session or requests
    try:
        with client.get(
            url,
            timeout=(10, 60),
            stream=True,
            headers={"User-Agent": "TransitOOH-Research/0.1"},
        ) as response:
            response.raise_for_status()
            if int(response.headers.get("Content-Length", 0)) > max_bytes:
                raise SourceError("Source exceeds declared download size limit")
            size = 0
            with part.open("wb") as out:
                for chunk in response.iter_content(65536):
                    size += len(chunk)
                    if size > max_bytes:
                        raise SourceError("Download exceeded size limit")
                    out.write(chunk)
            digest = sha256(part)
            if expected_sha256 and digest != expected_sha256:
                raise SourceError("Artifact checksum mismatch")
            part.replace(path)
            result = {
                "url": url,
                "path": str(path),
                "sha256": digest,
                "bytes": size,
                "status": "downloaded",
                "retrieved_at_utc": datetime.now(UTC).isoformat(),
                "tls_verified": True,
                "expected_sha256": expected_sha256,
                "etag": response.headers.get("ETag"),
            }
            write_json(str(path) + ".provenance.json", result)
            return result
    except (requests.RequestException, OSError, ValueError, SourceError) as e:
        part.unlink(missing_ok=True)
        # Do not log signed redirect URLs or secret-bearing exception strings.
        reason = str(e) if isinstance(e, SourceError) else type(e).__name__
        if isinstance(e, requests.HTTPError) and e.response is not None:
            reason += f" HTTP {e.response.status_code}"
        raise SourceError(f"Failed to acquire {url.split('?')[0]}: {reason}") from e


LADE_FILE = "data/delivery_jl-00000-of-00001-a4fbefe3c368583c.parquet"
LADE_HASH = "ed0296b83d84f739bb91ab3d3cf1a430cf71e3793e25ddf50f88aa3ef34b51fc"
AMAZON_BASE = "https://amazon-last-mile-challenges.s3.amazonaws.com/almrrc2021/"


def acquire_public(root="data/raw"):
    root = Path(root)
    results = []
    sources = [
        (
            "lade_jilin",
            f"https://huggingface.co/datasets/Cainiao-AI/LaDe-D/resolve/main/{LADE_FILE}",
            root / "lade_jilin.parquet",
            5_000_000,
            LADE_HASH,
        ),
        (
            "amazon_routes",
            AMAZON_BASE
            + "almrrc2021-data-evaluation/model_apply_inputs/eval_route_data.json",
            root / "amazon_eval_routes.json",
            45_000_000,
            "dfd8a198b9df5e3b194d3a268f6f442edcd77f028870d54a8d7397a7bc366466",
        ),
        (
            "amazon_sequences",
            AMAZON_BASE
            + "almrrc2021-data-evaluation/model_score_inputs/eval_actual_sequences.json",
            root / "amazon_eval_sequences.json",
            6_000_000,
            "30e924b5f263bd5e0a4bb58a756c8f6767b49d59a6bfa718ce26d2767a2c90e9",
        ),
    ]
    for name, url, path, limit, digest in sources:
        try:
            result = download(url, path, limit, digest)
            result["name"] = name
        except SourceError as e:
            result = {"name": name, "status": "failed", "error": str(e), "url": url}
        results.append(result)
    try:
        existing = root / "osm_seoul_map.osm"
        sidecar = Path(str(existing) + ".provenance.json")
        if existing.exists() and sidecar.exists():
            cached = json.loads(sidecar.read_text())
            if sha256(existing) != cached["sha256"]:
                raise SourceError("Cached OSM checksum mismatch")
            results.append({**cached, "status": "verified_cache"})
        else:
            results.append(acquire_osm_map(root))
    except SourceError as e:
        results.append({"name": "osm_seoul_api", "status": "failed", "error": str(e)})
    ledger = Path("reports/runs/public_acquisition.json")
    history = json.loads(ledger.read_text()) if ledger.exists() else []
    write_json(ledger, history + results)
    return results


def lade_events(frame):
    required = {
        "courier_id",
        "delivery_time",
        "delivery_gps_time",
        "delivery_gps_lat",
        "delivery_gps_lng",
        "city",
        "lat",
        "lng",
    }
    if required - set(frame):
        raise ValueError(f"Missing LaDe fields: {sorted(required - set(frame))}")
    d = frame.copy()
    d["event_time_local_raw"] = d.delivery_time
    d["gps_time_local_raw"] = d.delivery_gps_time
    # Timezone and CRS of these unzoned public fields must be externally confirmed.
    # Keep raw strings and identifier courier_id: never rename to vehicle_id.
    d["latitude"] = pd.to_numeric(d.delivery_gps_lat, errors="coerce")
    d["longitude"] = pd.to_numeric(d.delivery_gps_lng, errors="coerce")
    d["coordinate_reference_status"] = (
        "provider_lat_lng; paper states perturbation limited to 10m; datum unverified"
    )
    return provenance(
        d,
        "Cainiao-AI/LaDe-D delivery_jl",
        "public_observed",
        "courier_delivery_event_nearest_gps",
    )


def amazon_stops(routes, sequences=None):
    rows = []
    for route_id, route in routes.items():
        sequence = (sequences or {}).get(route_id, {}).get("actual", {})
        for stop_id, stop in route["stops"].items():
            rows.append(
                {
                    "route_id": route_id,
                    "stop_id": stop_id,
                    "station_code": route["station_code"],
                    "departure_date": route["date_YYYY_MM_DD"],
                    "departure_time_utc": route["departure_time_utc"],
                    "latitude": stop["lat"],
                    "longitude": stop["lng"],
                    "stop_type": stop["type"],
                    "zone_id": stop.get("zone_id"),
                    "sequence_index": sequence.get(stop_id),
                    "coordinate_reference_status": "WGS84; provider-obfuscated; no stop timestamp",
                }
            )
    return provenance(
        pd.DataFrame(rows),
        "Amazon Last Mile Routing Research Challenge evaluation",
        "public_observed",
        "obfuscated_route_stop",
    )


def osm_points(body):
    rows = []
    for el in body["elements"]:
        loc = el if "lat" in el else el.get("center", {})
        if "lat" not in loc:
            continue
        rows.append(
            {
                "osm_type": el["type"],
                "osm_id": el["id"],
                "latitude": loc["lat"],
                "longitude": loc["lon"],
                "amenity": el.get("tags", {}).get("amenity"),
                "poi_count": 1,
            }
        )
    return provenance(
        pd.DataFrame(rows),
        "OpenStreetMap contributors / Overpass",
        "public_observed",
        "mapped_amenity_centroid",
    )


def acquire_osm_map(root="data/raw"):
    """Small OSM API bbox, nodes only; no false claim of complete amenity coverage."""
    url = "https://www.openstreetmap.org/api/0.6/map?bbox=126.975,37.563,126.982,37.568"
    p = Path(root) / "osm_seoul_map.osm"
    result = download(url, p, 10_000_000)
    result.update(
        name="osm_seoul_api",
        license="ODbL-1.0",
        attribution="© OpenStreetMap contributors",
        observation_type="public_observed",
        observation_unit="mapped_amenity_nodes",
        coverage="bbox node amenities only; polygons excluded",
        bbox=[126.975, 37.563, 126.982, 37.568],
    )
    write_json(str(p) + ".provenance.json", result)
    return result


def osm_xml_points(path):
    root = ET.parse(path).getroot()
    rows = []
    for node in root.findall("node"):
        tags = {t.attrib["k"]: t.attrib["v"] for t in node.findall("tag")}
        if "amenity" not in tags:
            continue
        lon = float(node.attrib["lon"])
        lat = float(node.attrib["lat"])
        if not (126.975 <= lon <= 126.982 and 37.563 <= lat <= 37.568):
            continue
        rows.append(
            {
                "osm_id": node.attrib["id"],
                "latitude": lat,
                "longitude": lon,
                "amenity": tags["amenity"],
                "poi_count": 1,
                "element_last_edit": node.attrib.get("timestamp"),
            }
        )
    return provenance(
        pd.DataFrame(rows),
        "OpenStreetMap contributors / map API",
        "public_observed",
        "mapped_amenity_nodes",
    )
