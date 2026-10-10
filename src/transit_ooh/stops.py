"""Spatial dwell episodes; elapsed timestamps, never point count × nominal interval."""

from __future__ import annotations
import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment

STOP_COLS = [
    "vehicle_id",
    "start_time",
    "end_time",
    "dwell_seconds",
    "x",
    "y",
    "latitude",
    "longitude",
    "n_points",
    "observation_type",
]


def detect_stops(gps, radius_m=30, min_seconds=120):
    rows = []
    for vehicle, g in gps.groupby("vehicle_id", sort=True):
        g = g.reset_index(drop=True)
        xy = g[["x", "y"]].to_numpy()
        ts = g.timestamp.astype("int64").to_numpy() / 1e9
        valid = g.point_valid.to_numpy()
        links = g.interval_valid.to_numpy()
        i = 0
        while i < len(g):
            if not valid[i]:
                i += 1
                continue
            j = i + 1
            while (
                j < len(g)
                and links[j]
                and valid[j]
                and np.linalg.norm(xy[j] - xy[i]) <= radius_m
            ):
                j += 1
            end = j - 1
            if end > i and ts[end] - ts[i] >= min_seconds:
                part = g.iloc[i:j]
                rows.append(
                    {
                        "vehicle_id": vehicle,
                        "start_time": g.timestamp.iloc[i],
                        "end_time": g.timestamp.iloc[end],
                        "dwell_seconds": ts[end] - ts[i],
                        "x": part.x.median(),
                        "y": part.y.median(),
                        "latitude": part.latitude.median(),
                        "longitude": part.longitude.median(),
                        "n_points": len(part),
                        "observation_type": g.observation_type.iloc[0],
                    }
                )
                i = j
            else:
                i += 1
    return pd.DataFrame(rows, columns=STOP_COLS)


def evaluate_stops(predicted, truth, iou_threshold=0.5):
    """One-to-one maximum-IoU assignment, within vehicle. Zero prediction => recall 0."""
    matches = []
    for v, gt in truth.groupby("vehicle_id"):
        p = predicted[predicted.vehicle_id == v]
        if p.empty:
            continue
        p = p.reset_index(drop=True)
        gt = gt.reset_index(drop=True)
        ious = np.zeros((len(p), len(gt)))
        for i, a in p.iterrows():
            for j, b in gt.iterrows():
                overlap = max(
                    0.0,
                    (
                        min(a.end_time, b.end_time) - max(a.start_time, b.start_time)
                    ).total_seconds(),
                )
                union = max(
                    0.0,
                    (
                        max(a.end_time, b.end_time) - min(a.start_time, b.start_time)
                    ).total_seconds(),
                )
                ious[i, j] = overlap / union if union else 0
        # Maximize valid-match cardinality first, then IoU.
        r, c = linear_sum_assignment(
            -((ious >= iou_threshold).astype(float) * 1000 + ious)
        )
        for i, j in zip(r, c):
            if ious[i, j] >= iou_threshold:
                matches.append(
                    {
                        "vehicle_id": v,
                        "iou": ious[i, j],
                        "duration_error_seconds": p.iloc[i].dwell_seconds
                        - gt.iloc[j].dwell_seconds,
                    }
                )
    tp = len(matches)
    fp = len(predicted) - tp
    fn = len(truth) - tp
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {
        "true_episodes": len(truth),
        "predicted_episodes": len(predicted),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0,
        "matched_duration_mae_seconds": float(
            np.mean([abs(m["duration_error_seconds"]) for m in matches])
        )
        if matches
        else None,
        "true_dwell_seconds": float(truth.dwell_seconds.sum()),
        "predicted_dwell_seconds": float(predicted.dwell_seconds.sum()),
        "total_dwell_error_seconds": float(
            predicted.dwell_seconds.sum() - truth.dwell_seconds.sum()
        ),
    }, pd.DataFrame(matches)
