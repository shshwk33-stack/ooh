"""Explicit input contracts. Unknown units, CRS, and provenance are not inferred."""

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlparse

from . import PipelineError

REQUIRED_PROPERTIES = ("code", "name", "name_eng", "base_year")


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def canonical_json(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2,
                       allow_nan=False) + "\n").encode("utf-8")


def _reject_constant(value):
    raise PipelineError(f"JSON contains a non-finite number: {value}",
                        code="NON_FINITE_JSON_NUMBER")


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise PipelineError(f"Duplicate JSON object key: {key}", code="DUPLICATE_JSON_KEY")
        value[key] = item
    return value


def parse_json(data, *, label="input"):
    try:
        return json.loads(data.decode("utf-8-sig"), parse_constant=_reject_constant,
                          object_pairs_hook=_unique_object)
    except PipelineError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PipelineError(f"{label} is not valid UTF-8 JSON: {exc}",
                            code="INVALID_JSON") from exc


def load_metadata(path):
    return validate_metadata(parse_json(Path(path).read_bytes(), label="metadata"))


def _object(value, name):
    if not isinstance(value, dict):
        raise PipelineError(f"{name} must be an object", code="METADATA_SCHEMA")
    return value


def _text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise PipelineError(f"{name} must be a non-empty string",
                            code="METADATA_SCHEMA")
    return value


def validate_metadata(data):
    _object(data, "metadata")
    if data.get("schema_version") != "1.0":
        raise PipelineError("metadata.schema_version must be '1.0'",
                            code="METADATA_SCHEMA")
    if data.get("dataset_kind") != "administrative_boundary":
        raise PipelineError("Only administrative_boundary data is supported in Phase 1",
                            code="DATASET_KIND_UNSUPPORTED")
    if data.get("geometry_only") is not True:
        raise PipelineError("geometry_only must be true; no observed scores are inferred",
                            code="METADATA_SCHEMA")
    source = _object(data.get("source"), "source")
    if source.get("kind") != "PUBLIC_AGGREGATE":
        raise PipelineError("This real-boundary pipeline accepts PUBLIC_AGGREGATE only",
                            code="SOURCE_KIND_UNSUPPORTED")
    for key in ("name", "publisher", "url", "license"):
        _text(source.get(key), "source." + key)
    url = urlparse(source["url"])
    if url.scheme not in ("https", "http") or not url.netloc:
        raise PipelineError("source.url must be an explicit HTTP(S) provenance URL",
                            code="METADATA_SCHEMA")
    year = source.get("reference_year")
    if isinstance(year, bool) or not isinstance(year, (int, str)) or not re.fullmatch(r"\d{4}", str(year)):
        raise PipelineError("source.reference_year must be a four-digit year",
                            code="METADATA_SCHEMA")
    if not re.fullmatch(r"[a-fA-F0-9]{64}", str(source.get("sha256", ""))):
        raise PipelineError("source.sha256 must contain the input file SHA-256",
                            code="METADATA_SCHEMA")
    spatial = _object(data.get("spatial"), "spatial")
    if spatial.get("input_crs") != "EPSG:4326":
        raise PipelineError("An explicit EPSG:4326 input CRS contract is required",
                            code="CRS_UNSUPPORTED")
    if spatial.get("analysis_crs") != "EPSG:5179":
        raise PipelineError("The supported metric analysis CRS is EPSG:5179",
                            code="CRS_UNSUPPORTED")
    if spatial.get("coordinate_order") != "longitude_latitude":
        raise PipelineError("Coordinates must explicitly use longitude_latitude order",
                            code="AXIS_ORDER_UNSUPPORTED")
    _text(spatial.get("crs_basis"), "spatial.crs_basis")
    return data
