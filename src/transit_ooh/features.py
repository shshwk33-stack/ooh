"""Separate stop visits and elapsed moving presence; retain cluster units."""

import numpy as np
import pandas as pd

from .grids import Grid

METRICS = [
    "moving_seconds",
    "stop_seconds",
    "visit_frequency",
    "repeat_visits",
    "unique_vehicles",
    "active_days",
    "passages",
]


def next_local_hour(timestamp, timezone):
    local = timestamp.tz_convert(timezone)
    # Hour boundaries belong to the local clock (including half-hour offsets).
    remaining = 3600 - (local.minute * 60 + local.second + local.microsecond / 1e6)
    return timestamp + pd.Timedelta(seconds=remaining)


def extract_features(gps, stops, grid: Grid, candidates=None, timezone="Asia/Seoul"):
    records = []
    for vehicle, g in gps.groupby("vehicle_id", sort=True):
        g = g.sort_values("timestamp").reset_index(drop=True)
        events = stops[stops.vehicle_id == vehicle]
        is_stop = np.zeros(len(g), dtype=bool)
        for e in events.itertuples():
            is_stop |= (
                (g.timestamp > e.start_time) & (g.timestamp <= e.end_time)
            ).to_numpy()
            # Split stop duration at local hour boundaries for time-of-day validity.
            current = e.start_time
            while current < e.end_time:
                end = min(e.end_time, next_local_hour(current, timezone))
                local = current.tz_convert(timezone)
                records.append(
                    {
                        "vehicle_id": vehicle,
                        "date": str(local.date()),
                        "hour": local.hour,
                        "grid_id": grid.key(e.x, e.y),
                        "moving_seconds": 0.0,
                        "stop_seconds": (end - current).total_seconds(),
                        "visit_frequency": int(current == e.start_time),
                        "passages": 0,
                    }
                )
                current = end
        last_key = None
        for i in range(1, len(g)):
            row = g.iloc[i]
            prev = g.iloc[i - 1]
            if not row.interval_valid or is_stop[i]:
                last_key = None
                continue
            # Split interval at local hour boundaries; linear interpolation is explicitly estimated.
            current = prev.timestamp
            end_total = row.timestamp
            dt = (end_total - current).total_seconds()
            while current < end_total:
                end = min(end_total, next_local_hour(current, timezone))
                a = (current - prev.timestamp).total_seconds() / dt
                b = (end - prev.timestamp).total_seconds() / dt
                x0 = prev.x + (row.x - prev.x) * a
                y0 = prev.y + (row.y - prev.y) * a
                x1 = prev.x + (row.x - prev.x) * b
                y1 = prev.y + (row.y - prev.y) * b
                local = current.tz_convert(timezone)
                for key, fraction in grid.segment_parts(x0, y0, x1, y1):
                    records.append(
                        {
                            "vehicle_id": vehicle,
                            "date": str(local.date()),
                            "hour": local.hour,
                            "grid_id": key,
                            "moving_seconds": fraction
                            * (end - current).total_seconds(),
                            "stop_seconds": 0.0,
                            "visit_frequency": 0,
                            "passages": int(key != last_key),
                        }
                    )
                    last_key = key
                current = end
    cols = [
        "vehicle_id",
        "date",
        "hour",
        "grid_id",
        "moving_seconds",
        "stop_seconds",
        "visit_frequency",
        "passages",
    ]
    detail = pd.DataFrame(records, columns=cols)
    if not detail.empty:
        detail = detail.groupby(cols[:4], as_index=False)[cols[4:]].sum()
    return aggregate(detail, candidates), detail


def aggregate(detail, candidates=None):
    keys = sorted(set(candidates if candidates is not None else detail.grid_id))
    result = pd.DataFrame(index=pd.Index(keys, name="grid_id"))
    for f in ["moving_seconds", "stop_seconds", "visit_frequency", "passages"]:
        result[f] = detail.groupby("grid_id")[f].sum().reindex(keys, fill_value=0)
    visits = detail.groupby(["grid_id", "vehicle_id"]).visit_frequency.sum()
    result["repeat_visits"] = (
        visits.sub(1).clip(lower=0).groupby(level=0).sum().reindex(keys, fill_value=0)
    )
    result["unique_vehicles"] = (
        detail.groupby("grid_id").vehicle_id.nunique().reindex(keys, fill_value=0)
    )
    result["active_days"] = (
        detail.groupby("grid_id").date.nunique().reindex(keys, fill_value=0)
    )
    result["total_dwell_minutes"] = result.stop_seconds / 60
    result["presence_seconds"] = result.stop_seconds + result.moving_seconds
    return result.reset_index()
