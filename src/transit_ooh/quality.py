"""Audit original order before sorting; never bridge invalid GPS intervals."""

from __future__ import annotations
import numpy as np
import pandas as pd
from pyproj import Geod

REQUIRED = ["vehicle_id", "timestamp", "latitude", "longitude"]


def normalize_gps(
    frame,
    timezone="Asia/Seoul",
    max_gap_seconds=180,
    max_speed_kmh=130,
    max_accuracy_m=100,
):
    missing = set(REQUIRED) - set(frame)
    if missing:
        raise ValueError(f"Missing GPS columns: {sorted(missing)}")
    if "observation_type" not in frame or "source" not in frame:
        raise ValueError("GPS must carry explicit source and observation_type")
    if (
        "observation_unit" in frame
        and not frame.observation_unit.isin(
            ["vehicle_gps", "synthetic_vehicle_gps"]
        ).all()
    ):
        raise ValueError("Event/stop locations are not continuous vehicle GPS")
    d = frame.copy()
    d["input_row"] = np.arange(len(d))
    # Reject mixed provenance in a trajectory experiment.
    if d.observation_type.nunique() != 1:
        raise ValueError("Mixed observation types must be separate experiments")
    parsed = pd.to_datetime(d.timestamp, errors="coerce", format="mixed")
    if not isinstance(parsed.dtype, pd.DatetimeTZDtype):
        if parsed.dtype == object:
            raise ValueError("Mixed timezones: normalize explicitly before importing")
        parsed = parsed.dt.tz_localize(timezone, ambiguous="NaT", nonexistent="NaT")
    d["timestamp"] = parsed.dt.tz_convert("UTC")
    for c in ["latitude", "longitude"]:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    checks = {}
    checks["input_rows"] = len(d)
    checks["missing_required"] = int(d[REQUIRED].isna().any(axis=1).sum())
    valid_coord = d.latitude.between(-90, 90) & d.longitude.between(-180, 180)
    checks["invalid_coordinates"] = int((~valid_coord).sum())
    checks["negative_time_deltas_input_order"] = int(
        (
            d.groupby("vehicle_id", sort=False).timestamp.diff().dt.total_seconds() < 0
        ).sum()
    )
    checks["duplicate_vehicle_timestamp"] = int(
        d.duplicated(["vehicle_id", "timestamp"]).sum()
    )
    checks["negative_reported_speed"] = int(
        (
            pd.to_numeric(d.get("speed", pd.Series(dtype=float)), errors="coerce") < 0
        ).sum()
    )
    d = d.loc[valid_coord & ~d[REQUIRED].isna().any(axis=1)].copy()
    d["vehicle_id"] = d.vehicle_id.astype(str)
    d = (
        d.sort_values(["vehicle_id", "timestamp", "input_row"])
        .drop_duplicates(["vehicle_id", "timestamp"])
        .reset_index(drop=True)
    )
    prev = d.groupby("vehicle_id")[["latitude", "longitude", "timestamp"]].shift()
    dt = (d.timestamp - prev.timestamp).dt.total_seconds()
    _, _, dist = Geod(ellps="WGS84").inv(
        prev.longitude.to_numpy(),
        prev.latitude.to_numpy(),
        d.longitude.to_numpy(),
        d.latitude.to_numpy(),
    )
    d["dt_seconds"] = dt
    d["distance_m"] = dist
    d["speed_kmh"] = (
        np.divide(
            dist, dt.to_numpy(), out=np.full(len(d), np.nan), where=dt.to_numpy() > 0
        )
        * 3.6
    )
    jump = d.speed_kmh > max_speed_kmh
    accuracy = pd.to_numeric(
        d.get("accuracy", pd.Series(0, index=d.index)), errors="coerce"
    )
    d["point_valid"] = ~(jump | (accuracy > max_accuracy_m))
    d["interval_valid"] = (
        (dt > 0)
        & (dt <= max_gap_seconds)
        & ~jump
        & d.point_valid
        & d.groupby("vehicle_id").point_valid.shift(fill_value=False).astype(bool)
    )
    checks["gps_jump_intervals"] = int(jump.sum())
    checks["gap_intervals"] = int((dt > max_gap_seconds).sum())
    checks["poor_accuracy_points"] = int((accuracy > max_accuracy_m).sum())
    checks["retained_rows"] = len(d)
    checks["valid_intervals"] = int(d.interval_valid.sum())
    report = pd.DataFrame(
        [
            {
                "issue": k,
                "count": v,
                "observation_type": frame.observation_type.iloc[0]
                if len(frame)
                else "assumed",
            }
            for k, v in checks.items()
        ]
    )
    return d, report
