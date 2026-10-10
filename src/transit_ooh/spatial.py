"""Context joins only via projected geometry, with temporal/provenance guards."""

import pandas as pd

from .grids import Grid


def spatial_features(context, metadata, grid: Grid, candidates, gps):
    required = {
        "crs",
        "projected_crs",
        "valid_from",
        "valid_to",
        "observation_type",
        "complete_coverage",
        "bbox_projected",
    }
    if required - set(metadata):
        raise ValueError(
            f"Missing context metadata: {sorted(required - set(metadata))}"
        )
    if metadata["crs"] != "EPSG:4326" or metadata["projected_crs"] != grid.crs:
        raise ValueError("Explicit CRS conversion required before context join")
    if set(gps.observation_type) != {metadata["observation_type"]} or set(
        context.observation_type
    ) != {metadata["observation_type"]}:
        raise ValueError("Do not combine synthetic and observed context/trajectories")
    start, end = (
        pd.Timestamp(metadata["valid_from"]),
        pd.Timestamp(metadata["valid_to"]),
    )
    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError(
            "Context valid_from/valid_to must include an explicit timezone"
        )
    if start > end:
        raise ValueError("Context validity interval is reversed")
    if start > gps.timestamp.min() or end < gps.timestamp.max():
        raise ValueError("Context does not cover trajectory observation period")
    c = grid.project(context)
    features = [k for k in ["population", "poi_count"] if k in c]
    if not features:
        raise ValueError("No observed spatial features supplied")
    if c[features].isna().any().any() or (c[features] < 0).any().any():
        raise ValueError("Spatial features must be nonnegative and complete per point")
    agg = c.groupby("grid_id")[features].sum().reindex(candidates)
    x0, y0, x1, y1 = metadata["bbox_projected"]
    covered = []
    for k in candidates:
        a, b, c1, d = grid.bounds(k)
        covered.append(
            bool(
                metadata["complete_coverage"]
                and a >= x0 - 1e-6
                and b >= y0 - 1e-6
                and c1 <= x1 + 1e-6
                and d <= y1 + 1e-6
            )
        )
    agg["spatial_covered"] = covered
    agg.loc[agg.spatial_covered, features] = agg.loc[
        agg.spatial_covered, features
    ].fillna(0)
    agg.loc[~agg.spatial_covered, features] = float("nan")
    return agg.reset_index()
