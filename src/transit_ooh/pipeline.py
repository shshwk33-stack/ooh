"""Single deterministic analysis entry used by CLI, experiments, tests and UI."""

from dataclasses import dataclass

from .features import extract_features
from .grids import Grid
from .quality import normalize_gps
from .scoring import score
from .spatial import spatial_features
from .stops import detect_stops
from .synthetic import candidate_keys


@dataclass
class Analysis:
    gps: object
    stops: object
    features: object
    scores: object
    detail: object
    quality: object
    grid: Grid
    normalizer: object
    mobility_weight: float


def analyze(gps, config, context=None, context_meta=None, normalizer=None, grid=None):
    q, quality = normalize_gps(
        gps,
        **{
            k: config[k]
            for k in ["timezone", "max_gap_seconds", "max_speed_kmh", "max_accuracy_m"]
        },
        **{
            k: config[k]
            for k in ["gap_policy", "gap_multiplier", "max_adaptive_gap_seconds"]
            if k in config
        },
    )
    if q.empty:
        raise ValueError("No valid GPS observations remain")
    grid = grid or Grid(config["projected_crs"], config["grid_size_m"])
    q = grid.project(q)
    stops = detect_stops(
        q,
        config["stop_radius_m"],
        config["min_stop_seconds"],
        method=config.get("stop_detector", "robust"),
        max_radius_m=max(config["stop_radius_m"], config.get("max_stop_radius_m", 90)),
    )
    if stops.empty and q.interval_valid.any():
        quality.loc[len(quality)] = {
            "issue": "no_stops_despite_valid_intervals_inspect_sampling_and_thresholds",
            "count": 1,
            "observation_type": q.observation_type.iloc[0],
        }
    candidates = candidate_keys(context_meta, grid) if context_meta else None
    features, detail = extract_features(q, stops, grid, candidates, config["timezone"])
    if context is not None:
        spatial = spatial_features(context, context_meta, grid, features.grid_id, q)
        features = features.merge(spatial, on="grid_id", validate="one_to_one")
    scores, norm = score(features, config["mobility_weight"], normalizer)
    scores = scores.merge(
        grid.cells(scores.grid_id), on="grid_id", validate="one_to_one"
    )
    scores["source"] = q.source.iloc[0]
    scores["observation_type"] = q.observation_type.iloc[0]
    scores["score_type"] = "assumed_decision_index"
    scores["time_allocation"] = "estimated_linear_between_valid_fixes"
    return Analysis(
        q,
        stops,
        features,
        scores,
        detail,
        quality,
        grid,
        norm,
        config["mobility_weight"],
    )
