"""GPS CSV input validation; this module does not estimate research scores.

Source classification is an asserted provenance label, not proof of observation.
Synthetic fixtures retain an in-file data_type label to prevent accidental mixing.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import math
import os
from pathlib import Path
import platform
import shutil
import sys
import tempfile
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

VERSION = "gps-input-1.0.0"
REQUIRED = ("vehicle_id", "timestamp", "longitude", "latitude")
KINDS = {"OBSERVED_GPS", "SYNTHETIC"}


class GPSInputError(ValueError):
    pass


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _parse_metadata(raw):
    def reject_constant(value):
        raise GPSInputError(f"Non-finite JSON constant is forbidden: {value}")

    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise GPSInputError(f"Duplicate JSON metadata key: {key}")
            result[key] = value
        return result

    return json.loads(raw, object_pairs_hook=unique_object, parse_constant=reject_constant)


def _publish(stage, output):
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise GPSInputError("Output changed during processing; refusing to overwrite existing results")
    os.replace(stage, output)


def _distance_m(a, b):
    p1, p2 = math.radians(a[1]), math.radians(b[1])
    dp, dl = p2 - p1, math.radians(b[0] - a[0])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371008.8 * 2 * math.asin(math.sqrt(min(1, max(0, h))))


def validate_metadata(metadata, raw):
    if not isinstance(metadata, dict) or metadata.get("schema_version") != "1.0":
        raise GPSInputError("metadata.schema_version must be '1.0'")
    if metadata.get("dataset_kind") != "vehicle_positions":
        raise GPSInputError("metadata.dataset_kind must be vehicle_positions")
    source = metadata.get("source", {})
    if not isinstance(source, dict) or not isinstance(source.get("kind"), str) or source["kind"] not in KINDS:
        raise GPSInputError("source.kind must be OBSERVED_GPS or SYNTHETIC")
    for field in ("name", "sha256", "timezone", "provenance"):
        if not isinstance(source.get(field), str) or not source[field].strip():
            raise GPSInputError(f"source.{field} is required")
    if source["sha256"] != hashlib.sha256(raw).hexdigest():
        raise GPSInputError("source SHA-256 does not match CSV bytes")
    try:
        ZoneInfo(source["timezone"])
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise GPSInputError("source.timezone must name a valid IANA time zone") from exc
    spatial = metadata.get("spatial", {})
    if not isinstance(spatial, dict) or spatial.get("input_crs") != "EPSG:4326" or spatial.get("coordinate_order") != "longitude_latitude":
        raise GPSInputError("Explicit EPSG:4326 longitude_latitude input contract is required")
    if source["kind"] == "SYNTHETIC":
        generator = metadata.get("generator", {})
        if not isinstance(generator, dict) or not isinstance(generator.get("seed"), int) or isinstance(generator.get("seed"), bool) or not isinstance(generator.get("method"), str) or not generator["method"].strip():
            raise GPSInputError("Synthetic data requires generator.seed and generator.method")
    elif "generator" in metadata:
        raise GPSInputError("Generated fixture cannot be relabeled OBSERVED_GPS")
    return source["kind"]


def validate_csv(raw, metadata, max_speed_kmh=120):
    """Return canonical sorted observations and a strict, auditable quality report.

    Missing values, duplicates and invalid observations are rejected, never imputed.
    Sorting is reported and preserved as a documented transformation.
    """
    if not isinstance(max_speed_kmh, (int, float)) or isinstance(max_speed_kmh, bool) or not math.isfinite(max_speed_kmh) or max_speed_kmh <= 0:
        raise GPSInputError("max_speed_kmh must be finite and positive")
    max_speed_kmh = float(max_speed_kmh)
    kind = validate_metadata(metadata, raw)
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise GPSInputError("GPS CSV must be UTF-8") from exc
    reader = csv.DictReader(io.StringIO(text), strict=True)
    columns = reader.fieldnames
    if not columns or len(columns) != len(set(columns)):
        raise GPSInputError("CSV headers are missing or duplicated")
    missing = [field for field in REQUIRED if field not in columns]
    if missing:
        raise GPSInputError("Missing required columns: " + ", ".join(missing))
    if kind == "SYNTHETIC" and "data_type" not in columns:
        raise GPSInputError("SYNTHETIC input must retain an in-file data_type column")
    errors, rows, seen, instants = [], [], set(), {}
    missing_counts = {field: 0 for field in REQUIRED}
    original_order = []
    total_rows = 0
    for number, row in enumerate(reader, 2):
        total_rows += 1
        label = f"row {number}"
        row_errors = []
        if None in row or any(value is None for value in row.values()):
            row_errors.append("CSV field count does not match header")
        for field in REQUIRED:
            if not (row.get(field) or "").strip():
                missing_counts[field] += 1
                row_errors.append(f"missing {field}")
        if "data_type" in columns and row.get("data_type") != kind:
            row_errors.append("data_type does not match source.kind")
        if row_errors:
            errors.extend(f"{label}: {error}" for error in row_errors)
            continue
        vehicle = row["vehicle_id"].strip()
        try:
            stamp = datetime.fromisoformat(row["timestamp"].strip().replace("Z", "+00:00"))
            if stamp.tzinfo is None or stamp.utcoffset() is None:
                raise ValueError("UTC offset missing")
            utc = stamp.astimezone(timezone.utc)
            if stamp.utcoffset() != utc.astimezone(ZoneInfo(metadata["source"]["timezone"])).utcoffset():
                raise ValueError("UTC offset does not match declared source timezone")
        except (ValueError, OverflowError):
            errors.append(f"{label}: timestamp must be ISO8601 with explicit UTC offset consistent with source.timezone")
            continue
        try:
            lon, lat = float(row["longitude"]), float(row["latitude"])
            if not all(math.isfinite(v) for v in (lon, lat)) or not -180 <= lon <= 180 or not -90 <= lat <= 90:
                raise ValueError("invalid coordinate")
        except ValueError:
            errors.append(f"{label}: finite WGS84 longitude/latitude outside valid range or malformed")
            continue
        if (row.get("speed_kmh") or "").strip():
            try:
                speed = float(row["speed_kmh"])
                if not math.isfinite(speed) or speed < 0 or speed > max_speed_kmh:
                    raise ValueError("implausible speed")
            except ValueError:
                errors.append(f"{label}: speed_kmh must be finite and between 0 and {max_speed_kmh}")
                continue
        key = (vehicle, utc.isoformat(), lon, lat)
        instant = (vehicle, utc.isoformat())
        if key in seen:
            errors.append(f"{label}: duplicate observation")
        elif instant in instants:
            errors.append(f"{label}: conflicting positions at the same vehicle timestamp")
        seen.add(key)
        instants[instant] = (lon, lat)
        original_order.append((vehicle, utc))
        canonical = dict(row)
        canonical.update(vehicle_id=vehicle, timestamp=utc.isoformat().replace("+00:00", "Z"), data_type=kind)
        rows.append((vehicle, utc, lon, lat, number, canonical))
    if not rows and not errors:
        errors.append("CSV has no observations")
    rows.sort(key=lambda item: (item[0], item[1], item[2], item[3]))
    previous, max_inferred = {}, 0.0
    for vehicle, stamp, lon, lat, number, row in rows:
        if vehicle in previous:
            before, previous_lon, previous_lat = previous[vehicle]
            seconds = (stamp - before).total_seconds()
            if seconds > 0:
                speed = _distance_m((previous_lon, previous_lat), (lon, lat)) / seconds * 3.6
                max_inferred = max(max_inferred, speed)
                if speed > max_speed_kmh:
                    errors.append(f"row {number}: inferred speed {speed:.3f} km/h exceeds configured {max_speed_kmh} km/h")
        previous[vehicle] = stamp, lon, lat
    times = [row[1] for row in rows]
    warnings = ["source.kind is a provenance assertion; validation does not certify field observation", "No road map matching, stop detection, M/S/V scoring or Bootstrap was performed"]
    if kind == "SYNTHETIC":
        warnings.append("SYNTHETIC conceptual trajectories: not observed delivery GPS and not constrained to actual roads")
    report = {"status": "failed" if errors else "passed", "dataset_kind": "vehicle_positions", "source_kind": kind, "input_rows": total_rows, "observations": len(rows), "vehicles": len({r[0] for r in rows}), "missing_required": missing_counts, "missing_rate": {field: count / max(1, total_rows) for field, count in missing_counts.items()}, "input_was_sorted": original_order == sorted(original_order), "transformation": "sort by vehicle and UTC timestamp; normalize timestamps to UTC; trim vehicle ID whitespace; retain coordinate strings; no row deletion or value imputation", "max_speed_kmh": max_speed_kmh, "max_inferred_speed_kmh": round(max_inferred, 6), "period": {"start": min(times).isoformat() if times else None, "end": max(times).isoformat() if times else None}, "errors": errors, "warnings": warnings}
    return [row[-1] for row in rows], report, columns


def run_gps_pipeline(input_path, metadata_path, output_dir, max_speed_kmh=120):
    """Validate and publish all successful outputs atomically from a sibling stage.

    Validation/export failures publish quality and log files only. If the output
    location itself cannot be written, raise a clear error without changing it.
    """
    stage = None
    try:
        input_path, metadata_path, output_dir = Path(input_path).resolve(), Path(metadata_path).resolve(), Path(output_dir).resolve()
        if output_dir in (input_path, metadata_path) or output_dir in input_path.parents or output_dir in metadata_path.parents:
            raise GPSInputError("Output must not overlap input or metadata directories")
        if output_dir.exists() and (not output_dir.is_dir() or any(output_dir.iterdir())):
            raise GPSInputError("Output directory must be empty; existing results are never overwritten")
        output_dir.parent.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix=".atlas-gps-", dir=output_dir.parent))
    except (OSError, ValueError, TypeError) as exc:
        raise GPSInputError(f"Cannot prepare GPS output: {exc}") from exc
    quality = {"status": "failed", "errors": [], "module_version": VERSION}
    logs = []

    def write_logs():
        (stage / "processing_log.jsonl").write_text("".join(_canonical(row) + "\n" for row in logs), encoding="utf-8")

    try:
        if not input_path.is_file() or not metadata_path.is_file():
            raise GPSInputError("GPS input and metadata must exist and be regular files")
        raw = input_path.read_bytes()
        metadata_raw = metadata_path.read_bytes()
        metadata = _parse_metadata(metadata_raw)
        rows, quality, columns = validate_csv(raw, metadata, max_speed_kmh)
        logs.append({"stage": "validation", "status": quality["status"], "input_rows": quality["input_rows"], "source_kind": quality["source_kind"], "errors": quality["errors"]})
        if quality["errors"]:
            raise GPSInputError(f"GPS CSV validation failed with {len(quality['errors'])} error(s); see quality_report.json")
        _write_json(stage / "quality_report.json", quality)
        output_columns = list(columns)
        if "data_type" not in output_columns:
            output_columns.append("data_type")
        result = stage / "validated_positions.csv"
        with result.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=output_columns, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        params = {"module_version": VERSION, "input_sha256": hashlib.sha256(raw).hexdigest(), "metadata_sha256": hashlib.sha256(metadata_raw).hexdigest(), "max_speed_kmh": float(max_speed_kmh)}
        run_id = hashlib.sha256(_canonical(params).encode()).hexdigest()
        manifest = {**params, "run_id": run_id, "source_kind": metadata["source"]["kind"], "derived_kind": "DERIVED", "lineage": {"source_kind": metadata["source"]["kind"], "source_name": metadata["source"]["name"], "provenance": metadata["source"]["provenance"]}, "period": quality["period"], "outputs": {"validated_positions.csv": hashlib.sha256(result.read_bytes()).hexdigest(), "quality_report.json": hashlib.sha256((stage / "quality_report.json").read_bytes()).hexdigest()}, "model_results": {"mobility": None, "spatial": None, "integrated": None, "bootstrap": None}, "scope": "GPS input validation only"}
        _write_json(stage / "run_manifest.json", manifest)
        logs.append({"stage": "export", "status": "passed", "run_id": run_id, "outputs": sorted(manifest["outputs"])})
        write_logs()
        _write_json(stage / "execution.json", {"python": platform.python_version(), "platform": platform.platform(), "finished_at": datetime.now(timezone.utc).isoformat()})
        _publish(stage, output_dir)
        return manifest
    except Exception as exc:
        failure = exc if isinstance(exc, GPSInputError) else GPSInputError(f"GPS processing failed: {exc}")
        for path in stage.iterdir():
            if path.is_file():
                path.unlink()
        if not quality.get("errors"):
            quality["errors"] = [str(failure)]
        quality.update(status="failed", module_version=VERSION)
        try:
            _write_json(stage / "quality_report.json", quality)
            logs.append({"stage": "processing", "status": "failed", "errors": quality["errors"]})
            write_logs()
            _publish(stage, output_dir)
        except (OSError, GPSInputError) as report_error:
            raise GPSInputError(f"{failure}; could not publish failure report: {report_error}") from exc
        raise failure from exc
    finally:
        if stage.exists():
            shutil.rmtree(stage, ignore_errors=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--metadata", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-speed-kmh", type=float, default=120)
    args = parser.parse_args(argv)
    try:
        result = run_gps_pipeline(args.input, args.metadata, args.output, args.max_speed_kmh)
    except GPSInputError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps({"status": "passed", "run_id": result["run_id"], "source_kind": result["source_kind"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
