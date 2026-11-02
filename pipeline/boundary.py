"""Strict, non-repairing boundary validation and deterministic spatial exports."""

import csv
import io
import json
import math
import os
import platform
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from . import PipelineError, __version__
from .contracts import (REQUIRED_PROPERTIES, canonical_json, parse_json,
                        sha256_bytes, validate_metadata)

INPUT_CRS = "EPSG:4326"
ANALYSIS_CRS = "EPSG:5179"
ROUNDTRIP_TOLERANCE_DEG = 1e-8


def _dependencies():
    try:
        import pyproj
        import shapely
        from pyproj import CRS, Transformer
        from shapely.geometry import MultiPolygon, mapping, shape
        from shapely.geometry.polygon import orient
        from shapely.ops import transform
        from shapely.validation import explain_validity
        from shapely import wkt
    except ImportError as exc:
        raise PipelineError("Install the analysis requirements: pyproj and shapely are required",
                            code="DEPENDENCY_UNAVAILABLE") from exc
    return dict(pyproj=pyproj, shapely=shapely, CRS=CRS, Transformer=Transformer,
                MultiPolygon=MultiPolygon, mapping=mapping, shape=shape, orient=orient,
                transform=transform, explain_validity=explain_validity, wkt=wkt)


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _issue(message, code, **context):
    raise PipelineError(message, code=code, context=context)


def _rings(geometry, index):
    if not isinstance(geometry, dict) or geometry.get("type") not in ("Polygon", "MultiPolygon"):
        _issue("Only non-null Polygon/MultiPolygon geometries are supported", "GEOMETRY_TYPE", feature_index=index)
    coords = geometry.get("coordinates")
    polygons = [coords] if geometry["type"] == "Polygon" else coords
    if not isinstance(polygons, list) or not polygons:
        _issue("A geometry must contain at least one polygon", "EMPTY_GEOMETRY", feature_index=index)
    rings = []
    for polygon in polygons:
        if not isinstance(polygon, list) or not polygon:
            _issue("A polygon must contain an exterior ring", "EMPTY_GEOMETRY", feature_index=index)
        for ring in polygon:
            if not isinstance(ring, list) or len(ring) < 4:
                _issue("A linear ring requires at least four coordinates", "RING_SIZE", feature_index=index)
            for point in ring:
                if (not isinstance(point, list) or len(point) != 2 or
                        not all(_number(value) for value in point)):
                    _issue("Each coordinate must be exactly two finite numeric values", "COORDINATE_FORMAT", feature_index=index)
                if not (-180 <= point[0] <= 180 and -90 <= point[1] <= 90):
                    _issue("Coordinates exceed longitude/latitude bounds", "COORDINATE_RANGE", feature_index=index)
            if ring[0] != ring[-1]:
                _issue("Input rings must already be explicitly closed; automatic repair is prohibited", "UNCLOSED_RING", feature_index=index)
            if len({tuple(point) for point in ring[:-1]}) < 3:
                _issue("A ring requires at least three distinct vertices", "RING_SIZE", feature_index=index)
            rings.append(ring)
    return rings


def _declared_crs(data):
    if "crs" not in data:
        return None
    crs = data["crs"]
    properties = crs.get("properties") if isinstance(crs, dict) else None
    name = properties.get("name") if (isinstance(crs, dict) and crs.get("type") == "name"
                                      and isinstance(properties, dict)) else None
    supported = {"EPSG:4326", "urn:ogc:def:crs:EPSG::4326", "urn:ogc:def:crs:OGC:1.3:CRS84", "OGC:CRS84"}
    if name not in supported:
        _issue("The GeoJSON CRS declaration conflicts with the EPSG:4326 input contract", "CRS_MISMATCH")
    return name


def validate_feature_collection(data, metadata):
    """Return validated records and a quality summary without changing raw data."""
    validate_metadata(metadata)
    deps = _dependencies()
    if not isinstance(data, dict) or data.get("type") != "FeatureCollection":
        _issue("Input must be a GeoJSON FeatureCollection", "FEATURE_COLLECTION_REQUIRED")
    features = data.get("features")
    if not isinstance(features, list) or not features:
        _issue("FeatureCollection must contain features", "EMPTY_FEATURE_COLLECTION")
    declared = _declared_crs(data)
    warnings = []
    if declared is None:
        warnings.append({"code": "CRS_NOT_DECLARED_IN_SOURCE",
                         "message": "The source file has no CRS declaration. EPSG:4326 is an explicit processing contract, not independently verified official source metadata.",
                         "basis": metadata["spatial"]["crs_basis"]})
    license_text = metadata["source"]["license"]
    if license_text.strip().lower() in {"unknown", "미확인", "unverified", "not verified", "unspecified"}:
        warnings.append({"code": "LICENSE_UNVERIFIED", "message": "Source license/use conditions remain unverified; processing does not grant redistribution rights."})
    records, codes, names = [], set(), set()
    total_coordinates = 0
    for index, feature in enumerate(features):
        if not isinstance(feature, dict) or feature.get("type") != "Feature":
            _issue("Each feature must be a GeoJSON Feature", "FEATURE_SCHEMA", feature_index=index)
        props = feature.get("properties")
        if not isinstance(props, dict):
            _issue("Feature properties must be a non-null object", "PROPERTY_SCHEMA", feature_index=index)
        for key in REQUIRED_PROPERTIES:
            value = props.get(key)
            if key == "base_year":
                valid = (not isinstance(value, bool) and isinstance(value, (str, int)) and
                         len(str(value)) == 4 and str(value).isdigit())
            else:
                valid = isinstance(value, str) and bool(value.strip())
            if not valid:
                _issue(f"Required property {key} is missing or invalid", "PROPERTY_SCHEMA", feature_index=index, field=key)
        if str(props["base_year"]) != str(metadata["source"]["reference_year"]):
            _issue("Feature base_year conflicts with the metadata reference year", "REFERENCE_YEAR_MISMATCH", feature_index=index)
        if props["code"] in codes:
            _issue("Duplicate administrative region code", "DUPLICATE_CODE", feature_index=index, region_code=props["code"])
        codes.add(props["code"])
        if props["name"] in names:
            warnings.append({"code": "DUPLICATE_NAME", "message": "Administrative names repeat; region codes remain unique.", "name": props["name"]})
        names.add(props["name"])
        rings = _rings(feature.get("geometry"), index)
        try:
            geometry = deps["shape"](feature["geometry"])
        except (TypeError, ValueError) as exc:
            _issue(f"Geometry cannot be parsed: {exc}", "INVALID_GEOMETRY", feature_index=index)
        if geometry.is_empty or not geometry.is_valid or geometry.area <= 0:
            _issue("Invalid polygon topology: " + deps["explain_validity"](geometry), "INVALID_TOPOLOGY", feature_index=index)
        coordinates = sum(len(ring) for ring in rings)
        total_coordinates += coordinates
        records.append({"feature": feature, "properties": props, "geometry": geometry,
                        "rings": rings, "coordinate_count": coordinates})
    return records, {"status": "passed", "errors": [], "warnings": warnings,
                     "feature_count": len(records), "coordinate_count": total_coordinates,
                     "missing_rates": {key: 0.0 for key in REQUIRED_PROPERTIES},
                     "duplicate_region_codes": 0, "topology_valid_count": len(records),
                     "source_crs_declaration": declared, "input_crs": INPUT_CRS,
                     "axis_order": "longitude_latitude", "geometry_only": True}


def _transformers(deps):
    forward = deps["Transformer"].from_crs(INPUT_CRS, ANALYSIS_CRS, always_xy=True)
    inverse = deps["Transformer"].from_crs(ANALYSIS_CRS, INPUT_CRS, always_xy=True)
    x, y = forward.transform(127.5, 38.0, errcheck=True)
    if abs(x - 1000000.0) > 0.01 or abs(y - 2000000.0) > 0.01:
        _issue("EPSG:5179 origin check failed", "PROJECTION_CHECK_FAILED")
    return forward, inverse


def _metric_records(records, deps):
    forward, inverse = _transformers(deps)
    area = deps["CRS"].from_epsg(5179).area_of_use
    results = []
    max_error = 0.0
    for record in sorted(records, key=lambda item: item["properties"]["code"]):
        projected = deps["transform"](forward.transform, record["geometry"])
        if (projected.is_empty or not projected.is_valid or not math.isfinite(projected.area)
                or not math.isfinite(projected.length) or projected.area <= 0):
            _issue("Projected geometry is not a valid positive-area polygon", "PROJECTED_GEOMETRY_INVALID", region_code=record["properties"]["code"])
        for ring in record["rings"]:
            for lon, lat in ring:
                if not (area.west <= lon <= area.east and area.south <= lat <= area.north):
                    _issue("A coordinate is outside the metric analysis CRS area of use", "PROJECTION_AREA_UNSUPPORTED", region_code=record["properties"]["code"])
                x, y = forward.transform(lon, lat, errcheck=True)
                lon2, lat2 = inverse.transform(x, y, errcheck=True)
                error = max(abs(lon2 - lon), abs(lat2 - lat))
                if not all(math.isfinite(value) for value in (x, y, lon2, lat2)) or error > ROUNDTRIP_TOLERANCE_DEG:
                    _issue("Coordinate round-trip tolerance exceeded", "COORDINATE_ROUNDTRIP_FAILED", region_code=record["properties"]["code"])
                max_error = max(max_error, error)
        results.append({**record, "projected": projected,
                        "area_m2": projected.area, "perimeter_m": projected.length})
    return results, max_error


def _csv_bytes(columns, rows):
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def _output_safety(input_path, metadata_path, output_path):
    for source in (input_path, metadata_path):
        if not source.is_file():
            _issue("An input file does not exist or is not a regular file", "INPUT_NOT_FOUND", file=source.name)
        if source == output_path or output_path in source.parents:
            _issue("Output must not contain or overwrite an original input file", "OUTPUT_OVERWRITES_SOURCE")
    if output_path.exists() and (not output_path.is_dir() or any(output_path.iterdir())):
        _issue("Output must be a new or empty directory; existing results are never overwritten", "OUTPUT_NOT_EMPTY")


def _publish(stage, output):
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        _issue("Output changed during processing; refusing to overwrite it", "OUTPUT_NOT_EMPTY")
    os.replace(stage, output)


def run_pipeline(input_path, metadata_path, output_dir, region_code=None, region_prefix=None):
    """Validate and atomically publish geometry outputs; raise PipelineError on failure.

    Deterministic artifacts exclude execution timestamps and machine environment.
    On invalid inputs, only quality_report.json and processing_log.jsonl are
    published. An existing nonempty output directory is never changed.
    """
    source = Path(input_path).resolve()
    metadata_file = Path(metadata_path).resolve()
    output = Path(output_dir).resolve()
    _output_safety(source, metadata_file, output)
    output.parent.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc)
    stage = Path(tempfile.mkdtemp(prefix=".atlas-boundary-", dir=output.parent))
    logs = []
    source_hash = None
    metadata_hash = None
    quality = {"status": "failed", "errors": [], "warnings": [], "geometry_only": True}

    def log(event, **details):
        logs.append({"sequence": len(logs) + 1, "event": event, **details})

    def write_log():
        (stage / "processing_log.jsonl").write_bytes(b"".join(
            json.dumps(row, sort_keys=True, ensure_ascii=False, allow_nan=False).encode("utf-8") + b"\n" for row in logs))

    try:
        raw = source.read_bytes()
        metadata_raw = metadata_file.read_bytes()
        source_hash, metadata_hash = sha256_bytes(raw), sha256_bytes(metadata_raw)
        log("inputs_read", source_sha256=source_hash, metadata_sha256=metadata_hash)
        metadata = validate_metadata(parse_json(metadata_raw, label="metadata"))
        if source_hash != metadata["source"]["sha256"].lower():
            _issue("Input SHA-256 does not match the explicit source metadata", "SOURCE_HASH_MISMATCH")
        log("source_hash_verified")
        data = parse_json(raw)
        records, quality = validate_feature_collection(data, metadata)
        log("input_validated", feature_count=len(records))
        if region_code is not None and region_prefix is not None:
            _issue("Select an exact region code or a prefix, not both", "SELECTION_CONFLICT")
        if region_prefix is not None:
            if not isinstance(region_prefix, str) or not region_prefix.strip():
                _issue("Region prefix must be a non-empty string", "SELECTION_INVALID")
            selection = {"mode": "prefix", "value": region_prefix}
            matches = lambda record: record["properties"]["code"].startswith(region_prefix)
        else:
            region_code = "11140" if region_code is None else str(region_code)
            if not region_code.strip():
                _issue("Region code must be non-empty", "SELECTION_INVALID")
            selection = {"mode": "exact", "value": region_code}
            matches = lambda record: record["properties"]["code"] == region_code
        if not any(matches(record) for record in records):
            _issue("Requested region selection does not match this dataset", "REGION_NOT_FOUND", selection=selection)
        deps = _dependencies()
        metric, roundtrip_error = _metric_records(records, deps)
        chosen_records = [record for record in metric if matches(record)]
        selected_codes = [record["properties"]["code"] for record in chosen_records]
        log("metric_geometry_computed", analysis_crs=ANALYSIS_CRS)
        params = {"region_code": region_code, "region_prefix": region_prefix,
                  "selection": selection, "input_crs": INPUT_CRS,
                  "analysis_crs": ANALYSIS_CRS, "always_xy": True,
                  "roundtrip_tolerance_deg": ROUNDTRIP_TOLERANCE_DEG,
                  "topology_repair": False}
        identity = {"source_sha256": source_hash, "metadata_sha256": metadata_hash,
                    "pipeline_version": __version__, "parameters": params}
        run_id = sha256_bytes(canonical_json(identity))[:24]
        provenance = {"output_kind": "DERIVED", "source_kind": metadata["source"]["kind"],
                      "source_sha256": source_hash, "source_reference_year": metadata["source"]["reference_year"],
                      "dataset_kind": "administrative_boundary", "geometry_only": True,
                      "run_id": run_id}
        selected_features = []
        bounds = []
        for chosen in chosen_records:
            polygon = chosen["geometry"]
            if polygon.geom_type == "Polygon":
                polygon = deps["orient"](polygon, sign=1.0)
            else:
                polygon = deps["MultiPolygon"]([deps["orient"](part, sign=1.0) for part in polygon.geoms])
            bounds.append(polygon.bounds)
            selected_features.append({"type": "Feature", "properties": dict(chosen["properties"]),
                                      "geometry": deps["mapping"](polygon)})
        selected_bbox = [min(b[0] for b in bounds), min(b[1] for b in bounds),
                         max(b[2] for b in bounds), max(b[3] for b in bounds)]
        geojson = {"type": "FeatureCollection", "bbox": selected_bbox,
                   "provenance": provenance,
                   "features": selected_features}
        (stage / "mapo.geojson").write_bytes(canonical_json(geojson))
        columns = ["code", "name", "name_eng", "base_year", "area_m2", "perimeter_m", "geometry_type", "coordinate_count"]
        rows = [{**{key: record["properties"][key] for key in REQUIRED_PROPERTIES},
                 "area_m2": f'{record["area_m2"]:.6f}',
                 "perimeter_m": f'{record["perimeter_m"]:.6f}',
                 "geometry_type": record["geometry"].geom_type,
                 "coordinate_count": record["coordinate_count"]} for record in metric]
        (stage / "districts.csv").write_bytes(_csv_bytes(columns, rows))
        projected_columns = ["code", "name", "name_eng", "base_year", "crs", "area_m2", "perimeter_m", "geometry_wkt"]
        projected_rows = [{**{key: chosen["properties"][key] for key in REQUIRED_PROPERTIES},
                         "crs": ANALYSIS_CRS, "area_m2": f'{chosen["area_m2"]:.6f}',
                         "perimeter_m": f'{chosen["perimeter_m"]:.6f}',
                         "geometry_wkt": deps["wkt"].dumps(chosen["projected"], rounding_precision=9, trim=True)}
                          for chosen in chosen_records]
        (stage / "mapo.projected.csv").write_bytes(_csv_bytes(projected_columns, projected_rows))
        if selection["mode"] == "exact":
            chosen = chosen_records[0]
            selected_region = {"code": chosen["properties"]["code"], "name": chosen["properties"]["name"],
                               "area_m2": round(chosen["area_m2"], 6),
                               "perimeter_m": round(chosen["perimeter_m"], 6)}
        else:
            selected_region = {"code_prefix": region_prefix, "feature_count": len(chosen_records),
                               "sum_area_m2": round(sum(row["area_m2"] for row in chosen_records), 6),
                               "sum_feature_perimeter_m": round(sum(row["perimeter_m"] for row in chosen_records), 6),
                               "perimeter_note": "Sum of individual feature perimeters includes shared internal borders; it is not a dissolved district perimeter."}
        quality.update({"selected_region": selected_region,
                        "selection": {**selection, "feature_count": len(chosen_records), "codes": selected_codes},
                        "source_sha256": source_hash, "analysis_crs": ANALYSIS_CRS,
                        "max_roundtrip_error_deg": roundtrip_error,
                        "roundtrip_tolerance_deg": ROUNDTRIP_TOLERANCE_DEG,
                        "analysis_scores_generated": False, "bootstrap_performed": False,
                        "geometry_derivation": "Ring winding normalized for RFC 7946 output; no topology repair or coordinate correction."})
        (stage / "quality_report.json").write_bytes(canonical_json(quality))
        log("outputs_ready", selection=selection, selected_codes=selected_codes,
            output_kind="DERIVED", geometry_only=True)
        write_log()
        output_hashes = {path.name: sha256_bytes(path.read_bytes()) for path in sorted(stage.iterdir())}
        manifest = {"schema_version": "1.0", "run_id": run_id, "pipeline_version": __version__,
                    "output_kind": "DERIVED", "dataset_kind": "administrative_boundary", "geometry_only": True,
                    "source": dict(metadata["source"]), "metadata_sha256": metadata_hash,
                    "spatial_contract": dict(metadata["spatial"]), "parameters": params,
                    "selected_codes": selected_codes,
                    "analysis_scores_generated": False, "bootstrap_performed": False,
                    "outputs": output_hashes,
                    "scope": "Validated historical administrative geometry only. No GPS, traffic, population, POI, mobility/spatial/integrated scores or statistical validation."}
        (stage / "run_manifest.json").write_bytes(canonical_json(manifest))
        execution = {"run_id": run_id, "started_at": started.isoformat(),
                     "completed_at": datetime.now(timezone.utc).isoformat(),
                     "python": sys.version, "platform": platform.platform(),
                     "pyproj": deps["pyproj"].__version__, "shapely": deps["shapely"].__version__,
                     "proj": deps["pyproj"].proj_version_str,
                     "input_filename": source.name, "metadata_filename": metadata_file.name,
                     "deterministic_artifacts": sorted([*output_hashes, "run_manifest.json"]),
                     "note": "Execution context is intentionally excluded from deterministic analysis artifacts."}
        (stage / "execution.json").write_bytes(canonical_json(execution))
        _publish(stage, output)
        return manifest
    except Exception as exc:
        failure = exc if isinstance(exc, PipelineError) else PipelineError(str(exc), code="PROCESSING_FAILED")
        # A calculation failure must never leave a usable-looking partial result.
        for path in stage.iterdir():
            if path.is_file():
                path.unlink()
        quality.update({"status": "failed", "errors": [failure.issue()],
                        "source_sha256": source_hash, "analysis_scores_generated": False,
                        "bootstrap_performed": False})
        (stage / "quality_report.json").write_bytes(canonical_json(quality))
        log("processing_failed", **failure.issue())
        write_log()
        try:
            _publish(stage, output)
        except PipelineError:
            shutil.rmtree(stage, ignore_errors=True)
        if failure is exc:
            raise
        raise failure from exc
    finally:
        if stage.exists():
            shutil.rmtree(stage, ignore_errors=True)
