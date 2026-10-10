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
    gap_policy="fixed",
    gap_multiplier=3.0,
    max_adaptive_gap_seconds=900,
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
    if gap_policy not in {"fixed", "adaptive"}:
        raise ValueError("gap_policy must be fixed or adaptive")
    if max_gap_seconds <= 0 or gap_multiplier < 1:
        raise ValueError("Positive gap limit and multiplier >= 1 required")
    # Remove only a geometrically isolated spike with valid normal neighbours.
    # Recompute all intervals afterward, bounded by the same gap policy below.
    geod = Geod(ellps="WGS84")
    spikes = []
    for _, g in d.groupby("vehicle_id", sort=False):
        if len(g) < 5:
            continue
        for pos in range(2, len(g) - 2):
            before, point, after = g.iloc[pos - 1], g.iloc[pos], g.iloc[pos + 1]
            dt1 = (point.timestamp - before.timestamp).total_seconds()
            dt2 = (after.timestamp - point.timestamp).total_seconds()
            dist1 = geod.inv(
                before.longitude, before.latitude, point.longitude, point.latitude
            )[2]
            dist2 = geod.inv(
                point.longitude, point.latitude, after.longitude, after.latitude
            )[2]
            bridge = geod.inv(
                before.longitude, before.latitude, after.longitude, after.latitude
            )[2]
            if (
                dt1 > 0
                and dt2 > 0
                and dist1 / dt1 * 3.6 > max_speed_kmh
                and dist2 / dt2 * 3.6 > max_speed_kmh
                and bridge / (dt1 + dt2) * 3.6 <= max_speed_kmh
            ):
                spikes.append(point.name)
    checks["isolated_spike_points_removed"] = len(spikes)
    d = d.drop(index=spikes).reset_index(drop=True)
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
    nominal = (
        d.assign(positive_dt=dt.where(dt > 0))
        .groupby("vehicle_id")
        .positive_dt.transform("median")
    )
    limits = pd.Series(float(max_gap_seconds), index=d.index)
    if gap_policy == "adaptive":
        # Do not turn multi-hour/day gaps into evidence: cap the inferred limit.
        limits = (
            (gap_multiplier * nominal)
            .clip(lower=max_gap_seconds, upper=max_adaptive_gap_seconds)
            .fillna(max_gap_seconds)
        )
    d["gap_limit_seconds"] = limits
    d["nominal_sample_seconds"] = nominal
    accuracy = pd.to_numeric(
        d.get("accuracy", pd.Series(0, index=d.index)), errors="coerce"
    )
    d["point_valid"] = ~(jump | (accuracy > max_accuracy_m))
    d["interval_valid"] = (
        (dt > 0)
        & (dt <= limits)
        & ~jump
        & d.point_valid
        & d.groupby("vehicle_id").point_valid.shift(fill_value=False).astype(bool)
    )
    checks["gps_jump_intervals"] = int(jump.sum())
    checks["gap_intervals"] = int((dt > limits).sum())
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
