"""Explicit provenance, portable tables, and immutable run manifests."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import pandas as pd
import yaml

TYPES = {"real_observed", "public_observed", "synthetic", "estimated", "assumed"}


def load_config(path="configs/default.yaml"):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def read_table(path):
    p = Path(path)
    if p.suffix.lower() == ".parquet":
        return pd.read_parquet(p)
    if p.suffix.lower() == ".csv":
        return pd.read_csv(p)
    if p.suffix.lower() == ".xlsx":
        return pd.read_excel(p, engine="openpyxl")
    raise ValueError("Expected CSV, Excel (.xlsx), or Parquet")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path, value):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    def clean(v):
        if isinstance(v, dict):
            return {str(k): clean(x) for k, x in v.items()}
        if isinstance(v, (list, tuple)):
            return [clean(x) for x in v]
        if isinstance(v, float) and not math.isfinite(v):
            return None
        if hasattr(v, "item"):
            return clean(v.item())
        return v

    p.write_text(
        json.dumps(
            clean(value), indent=2, ensure_ascii=False, default=str, allow_nan=False
        ),
        encoding="utf-8",
    )


def provenance(frame, source, observation_type, observation_unit):
    if observation_type not in TYPES:
        raise ValueError(f"Unknown observation_type: {observation_type}")
    out = frame.copy()
    out["source"] = source
    out["observation_type"] = observation_type
    out["observation_unit"] = observation_unit
    return out


def save_table(frame, path, observation_type=None):
    out = frame.copy()
    if observation_type is not None:
        out["observation_type"] = observation_type
    if "observation_type" not in out:
        raise ValueError("Every exported research table needs observation_type")
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.suffix == ".parquet":
        out.to_parquet(p, index=False)
    else:
        out.to_csv(p, index=False)
