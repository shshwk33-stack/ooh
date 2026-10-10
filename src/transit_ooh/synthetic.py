"""Independent, labelled motion schedules and geometry-based synthetic context."""

from __future__ import annotations

import numpy as np
import pandas as pd
from pyproj import Transformer

from .grids import Grid
from .io import provenance


def generate(
    seed=42,
    vehicles=6,
    days=6,
    sample_seconds=30,
    noise_m=5,
    start_date="2026-09-21",
    irregular=False,
    dropout=0.0,
    scenario="legacy",
    scenario_seed=1001,
    correlated_noise=False,
    accuracy_mode="reported",
):
    if vehicles < 1 or days < 1 or sample_seconds <= 0:
        raise ValueError("Positive vehicles, days and sample interval required")
    if noise_m < 0 or not 0 <= dropout < 1:
        raise ValueError("Invalid noise/dropout")
    rng = np.random.default_rng(seed)
    if scenario not in {"legacy", "mixed_delivery", "slow_traffic", "warehouse"}:
        raise ValueError("Unknown synthetic scenario")
    if accuracy_mode not in {"reported", "missing", "overconfident"}:
        raise ValueError("Unknown accuracy mode")
    scene_rng = np.random.default_rng(scenario_seed)
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
    if scenario != "legacy":
        sites += scene_rng.uniform(-70, 70, sites.shape)
    rows = []
    truth = []
    schedule = []
    for v in range(vehicles):
        for day in range(days):
            base = pd.Timestamp(start_date, tz="Asia/Seoul") + pd.Timedelta(
                days=day, hours=8 + (v % 3) * 2
            )
            route = [(v * 3 + day // 3 + j * 5) % len(sites) for j in range(6)]
            if scenario != "legacy":
                route = scene_rng.choice(len(sites), size=6, replace=False).tolist()
                base += pd.Timedelta(minutes=int(scene_rng.integers(-25, 26)))
            t = 0.0
            segments = []
            for j, site in enumerate(route):
                dur = float(360 + 120 * ((v + j + day) % 5))
                if scenario != "legacy":
                    dur = float(scene_rng.choice([60, 90, 120, 180, 300, 600, 900]))
                    if scenario == "warehouse" and j == 0:
                        dur = 1800.0
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
                        "x": float(sites[site][0]),
                        "y": float(sites[site][1]),
                        "observation_type": "synthetic",
                    }
                )
                if j < len(route) - 1:
                    nxt = sites[route[j + 1]]
                    mid = (sites[site] + nxt) / 2
                    dur_move = max(180.0, float(np.linalg.norm(nxt - sites[site]) / 4))
                    if scenario == "slow_traffic":
                        dur_move = float(
                            np.linalg.norm(nxt - sites[site])
                            / scene_rng.uniform(0.4, 1.2)
                        )
                    segments.append((t, t + dur_move / 2, sites[site], mid, "move"))
                    t += dur_move / 2
                    signal = (
                        45.0
                        if scenario == "legacy"
                        else float(scene_rng.choice([30, 60, 120, 180]))
                    )
                    segments.append((t, t + signal, mid, mid, "signal_stop"))
                    if signal >= 120:
                        truth.append(
                            {
                                "vehicle_id": f"S{v:02}",
                                "start_time": (
                                    base + pd.Timedelta(seconds=t)
                                ).tz_convert("UTC"),
                                "end_time": (
                                    base + pd.Timedelta(seconds=t + signal)
                                ).tz_convert("UTC"),
                                "dwell_seconds": signal,
                                "site_id": -1,
                                "stop_kind": "signal_stop",
                                "x": float(mid[0]),
                                "y": float(mid[1]),
                                "observation_type": "synthetic",
                            }
                        )
                    t += signal
                    segments.append((t, t + dur_move / 2, mid, nxt, "move"))
                    t += dur_move / 2
            times = np.arange(0, t + 1e-6, sample_seconds)
            if irregular and len(times) > 2:
                times[1:-1] += rng.uniform(-0.3, 0.3, len(times) - 2) * sample_seconds
                times = np.sort(times)
            if dropout:
                times = times[rng.random(len(times)) >= dropout]
            previous_noise = np.zeros(2)
            for tm in times:
                seg = next((s for s in segments if s[0] <= tm <= s[1]), segments[-1])
                a, b, p, q, state = seg
                xy = p + (q - p) * ((tm - a) / (b - a))
                error = rng.normal(0, noise_m, 2)
                if correlated_noise:
                    error = 0.8 * previous_noise + 0.6 * error
                previous_noise = error
                xy = xy + error
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
                        "accuracy": (
                            noise_m * 2
                            if accuracy_mode == "reported"
                            else (5.0 if accuracy_mode == "overconfident" else np.nan)
                        ),
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
                        "x_start": float(p[0]),
                        "y_start": float(p[1]),
                        "x_end": float(q[0]),
                        "y_end": float(q[1]),
                        "scenario": scenario,
                        "scenario_seed": scenario_seed,
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
        "synthetic_schedule_v1"
        if scenario == "legacy"
        else f"synthetic_schedule_v2:{scenario}:{scenario_seed}",
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
        "scenario": scenario,
        "scenario_seed": scenario_seed,
        "truth_scope": "physical_stationary_episodes_at_least_120s; includes_long_signals; not_delivery_purpose_classification",
    }
    truth = pd.DataFrame(truth)
    truth = truth[truth.dwell_seconds >= 120].reset_index(drop=True)
    return gps, truth, context, meta, pd.DataFrame(schedule)


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
