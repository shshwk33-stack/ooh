"""Single deterministic analysis entry used by CLI, experiments, tests and UI."""

from dataclasses import dataclass
from .quality import normalize_gps
from .grids import Grid
from .stops import detect_stops
from .features import extract_features
from .spatial import spatial_features
from .scoring import score
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
    )
    if q.empty:
        raise ValueError("No valid GPS observations remain")
    grid = grid or Grid(config["projected_crs"], config["grid_size_m"])
    q = grid.project(q)
    stops = detect_stops(q, config["stop_radius_m"], config["min_stop_seconds"])
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
