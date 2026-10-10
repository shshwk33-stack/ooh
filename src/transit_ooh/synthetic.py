"""Independent, labelled motion schedules and geometry-based synthetic context."""

from __future__ import annotations
import numpy as np
import pandas as pd
from pyproj import Transformer
from .io import provenance
from .grids import Grid


def generate(
    seed=42,
    vehicles=6,
    days=6,
    sample_seconds=30,
    noise_m=5,
    start_date="2026-09-21",
    irregular=False,
    dropout=0.0,
):
    if vehicles < 1 or days < 1 or sample_seconds <= 0:
        raise ValueError("Positive vehicles, days and sample interval required")
    if noise_m < 0 or not 0 <= dropout < 1:
        raise ValueError("Invalid noise/dropout")
    rng = np.random.default_rng(seed)
    to = Transformer.from_crs(4326, 32652, always_xy=True)
    back = Transformer.from_crs(32652, 4326, always_xy=True)
    cx, cy = to.transform(126.978, 37.5665)
    origin = (np.floor(cx / 200) * 200 - 600, np.floor(cy / 200) * 200 - 600)
    sites = np.array(
        [
            (origin[0] + x, origin[1] + y)
            for x, y in [
                (100, 100),
                (500, 100),
                (900, 100),
                (1300, 100),
                (100, 500),
                (500, 500),
                (900, 500),
                (1300, 500),
                (100, 900),
                (500, 900),
                (900, 900),
                (1300, 900),
                (100, 1300),
                (500, 1300),
                (900, 1300),
                (1300, 1300),
            ]
        ]
    )
    rows = []
    truth = []
    schedule = []
    for v in range(vehicles):
        for day in range(days):
            base = pd.Timestamp(start_date, tz="Asia/Seoul") + pd.Timedelta(
                days=day, hours=8 + (v % 3) * 2
            )
            route = [(v * 3 + day // 3 + j * 5) % len(sites) for j in range(6)]
            t = 0.0
            segments = []
            for j, site in enumerate(route):
                dur = float(360 + 120 * ((v + j + day) % 5))
                start = t
                t += dur
                segments.append((start, t, sites[site], sites[site], "delivery_stop"))
                truth.append(
                    {
                        "vehicle_id": f"S{v:02}",
                        "start_time": (base + pd.Timedelta(seconds=start)).tz_convert(
                            "UTC"
                        ),
                        "end_time": (base + pd.Timedelta(seconds=t)).tz_convert("UTC"),
                        "dwell_seconds": dur,
                        "site_id": site,
                        "stop_kind": "delivery_stop",
                        "observation_type": "synthetic",
                    }
                )
                if j < len(route) - 1:
                    nxt = sites[route[j + 1]]
                    mid = (sites[site] + nxt) / 2
                    dur_move = max(180.0, float(np.linalg.norm(nxt - sites[site]) / 4))
                    segments.append((t, t + dur_move / 2, sites[site], mid, "move"))
                    t += dur_move / 2
                    segments.append((t, t + 45, mid, mid, "signal_stop"))
                    t += 45
                    segments.append((t, t + dur_move / 2, mid, nxt, "move"))
                    t += dur_move / 2
            times = np.arange(0, t + 1e-6, sample_seconds)
            if irregular and len(times) > 2:
                times[1:-1] += rng.uniform(-0.3, 0.3, len(times) - 2) * sample_seconds
                times = np.sort(times)
            if dropout:
                times = times[rng.random(len(times)) >= dropout]
            for tm in times:
                seg = next((s for s in segments if s[0] <= tm <= s[1]), segments[-1])
                a, b, p, q, state = seg
                xy = p + (q - p) * ((tm - a) / (b - a))
                xy = xy + rng.normal(0, noise_m, 2)
                lon, lat = back.transform(*xy)
                rows.append(
                    {
                        "vehicle_id": f"S{v:02}",
                        "timestamp": (
                            base + pd.Timedelta(seconds=float(tm))
                        ).tz_convert("UTC"),
                        "latitude": lat,
                        "longitude": lon,
                        "truth_state": state,
                        "accuracy": noise_m * 2,
                        "route_id": f"S{v:02}-D{day}",
                    }
                )
            for a, b, p, q, state in segments:
                schedule.append(
                    {
                        "vehicle_id": f"S{v:02}",
                        "date": str(base.date()),
                        "start_seconds": a,
                        "end_seconds": b,
                        "state": state,
                    }
                )
    # A separate RNG makes the spatial field invariant to GPS sampling and noise.
    spatial_rng = np.random.default_rng(20260921)
    n = 400
    x = origin[0] + spatial_rng.uniform(0, 1600, n)
    y = origin[1] + spatial_rng.uniform(0, 1600, n)
    lon, lat = back.transform(x, y)
    context = provenance(
        pd.DataFrame(
            {
                "longitude": lon,
                "latitude": lat,
                "population": spatial_rng.poisson(20 + 60 * (x - origin[0]) / 1600, n),
                "poi_count": np.ones(n, dtype=int),
            }
        ),
        "synthetic_independent_spatial_field",
        "synthetic",
        "synthetic_spatial_point",
    )
    gps = provenance(
        pd.DataFrame(rows),
        "synthetic_schedule_v1",
        "synthetic",
        "synthetic_vehicle_gps",
    )
    meta = {
        "source": "synthetic_independent_spatial_field",
        "observation_type": "synthetic",
        "region": "Seoul-synthetic-area",
        "crs": "EPSG:4326",
        "projected_crs": "EPSG:32652",
        "bbox_projected": [origin[0], origin[1], origin[0] + 1600, origin[1] + 1600],
        "valid_from": str(gps.timestamp.min()),
        "valid_to": str(gps.timestamp.max()),
        "complete_coverage": True,
        "license": "Project-generated synthetic data; no empirical claim",
        "seed": seed,
        "context_seed": 20260921,
    }
    return gps, pd.DataFrame(truth), context, meta, pd.DataFrame(schedule)


def candidate_keys(meta, grid: Grid):
    x0, y0, x1, y1 = meta["bbox_projected"]
    # Enumerate intersecting cells. Coverage check excludes partial edge cells for shifted grids.
    keys = {
        grid.key(x, y)
        for x in np.arange(x0, x1 + grid.size, grid.size / 2)
        for y in np.arange(y0, y1 + grid.size, grid.size / 2)
    }
    return sorted(
        k
        for k in keys
        if (
            lambda b: (
                b[0] >= x0 - 1e-6
                and b[1] >= y0 - 1e-6
                and b[2] <= x1 + 1e-6
                and b[3] <= y1 + 1e-6
            )
        )(grid.bounds(k))
    )
