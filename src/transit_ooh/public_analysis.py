"""Separate descriptive studies of actual public observations, no inferred dwell."""

import json
from pathlib import Path
import pandas as pd
from .sources import amazon_stops, lade_events, osm_xml_points
from .io import save_table, write_json, sha256
from .grids import Grid


PUBLIC_OUTPUTS = {
    "amazon": ["public_amazon_station_summary", "public_amazon_spatial_coverage"],
    "lade": [
        "public_lade_event_summary",
        "public_lade_aoi_stability",
        "public_lade_bootstrap",
        "public_lade_monthly_stability",
    ],
    "osm": ["public_osm_amenity_summary", "public_osm_grid_counts"],
}


def clear_unavailable_outputs(root, output):
    """Remove only this generator's stale outputs, never another user's files."""
    available = {
        "amazon": (root / "amazon_eval_routes.json").exists(),
        "lade": any(
            (root / p).exists()
            for p in ["lade_jilin.parquet", "lade_jilin_preview.json"]
        ),
        "osm": (root / "osm_seoul_map.osm").exists(),
    }
    for source, names in PUBLIC_OUTPUTS.items():
        missing = names if not available[source] else []
        if source == "lade" and not (root / "lade_jilin.parquet").exists():
            missing = list(set(missing + names[1:]))
        for name in missing:
            (output / "tables" / f"{name}.csv").unlink(missing_ok=True)
        figure = {
            "amazon": "public_amazon_station_summary",
            "lade": "public_lade_event_stability",
            "osm": "public_osm_amenity_summary",
        }[source]
        if missing:
            for ext in ["png", "svg"]:
                (output / "figures" / f"{figure}.{ext}").unlink(missing_ok=True)


def analyze_public(root="data/raw", output="reports"):
    root = Path(root)
    output = Path(output)
    tables = output / "tables"
    tables.mkdir(parents=True, exist_ok=True)
    clear_unavailable_outputs(root, output)
    processed = root.parent / "processed"
    processed.mkdir(parents=True, exist_ok=True)
    summary = {}
    amazon = root / "amazon_eval_routes.json"
    if amazon.exists():
        routes = json.loads(amazon.read_text())
        p = root / "amazon_eval_sequences.json"
        sequences = json.loads(p.read_text()) if p.exists() else None
        stops = amazon_stops(routes, sequences)
        stops.to_parquet(processed / "amazon_stops.parquet", index=False)
        drop = stops[stops.stop_type == "Dropoff"]
        counts = (
            drop.groupby(["station_code", "route_id"])
            .size()
            .rename("dropoff_count")
            .reset_index()
        )
        station = (
            counts.groupby("station_code")
            .agg(
                routes=("route_id", "nunique"),
                dropoff_records=("dropoff_count", "sum"),
                median_dropoffs_per_route=("dropoff_count", "median"),
                min_dropoffs_per_route=("dropoff_count", "min"),
                max_dropoffs_per_route=("dropoff_count", "max"),
            )
            .reset_index()
        )
        dates = (
            stops.groupby("station_code")
            .agg(
                first_departure_date=("departure_date", "min"),
                last_departure_date=("departure_date", "max"),
            )
            .reset_index()
        )
        station = station.merge(dates, on="station_code")
        station["observation_unit"] = "obfuscated_route_stop"
        station["source"] = "Amazon LMRRC evaluation 2018"
        save_table(
            station, tables / "public_amazon_station_summary.csv", "public_observed"
        )
        # Within-station 200m visit density; different metro CRSs never merged.
        coverage = []
        for code, d in drop.groupby("station_code"):
            lon = d.longitude.median()
            lat = d.latitude.median()
            zone = int((lon + 180) // 6) + 1
            crs = f"EPSG:{32600 + zone if lat >= 0 else 32700 + zone}"
            g = Grid(crs, 200)
            projected = g.project(d)
            cell = projected.groupby("grid_id").agg(
                stop_records=("stop_id", "size"),
                routes=("route_id", "nunique"),
                days=("departure_date", "nunique"),
            )
            coverage.append(
                {
                    "station_code": code,
                    "crs": crs,
                    "grid_size_m": 200,
                    "occupied_cells": len(cell),
                    "median_stop_records_per_cell": cell.stop_records.median(),
                    "cells_multiple_routes": int((cell.routes > 1).sum()),
                    "coordinate_limitation": "provider_obfuscation; grid assignments approximate",
                    "dwell_available": False,
                }
            )
        save_table(
            pd.DataFrame(coverage),
            tables / "public_amazon_spatial_coverage.csv",
            "public_observed",
        )
        summary["amazon"] = {
            "status": "analyzed",
            "routes": len(routes),
            "stop_records": len(stops),
            "dropoff_records": len(drop),
            "stations": int(stops.station_code.nunique()),
            "period": [
                str(stops.departure_date.min()),
                str(stops.departure_date.max()),
            ],
            "sequence_coverage": float(stops.sequence_index.notna().mean()),
            "source_sha256": sha256(amazon),
            "observation_type": "public_observed",
            "unit": "obfuscated_route_stop",
            "continuous_vehicle_gps": False,
            "stop_arrival_or_dwell_time_available": False,
            "integration_with_seoul": "forbidden_geography_and_period_mismatch",
        }
    else:
        summary["amazon"] = {"status": "not_acquired"}
    lade = root / "lade_jilin.parquet"
    preview = root / "lade_jilin_preview.json"
    if lade.exists() or preview.exists():
        if lade.exists():
            raw = pd.read_parquet(lade)
            sampling = "full_jilin_partition"
            source = lade
        else:
            raw = pd.DataFrame(
                [r["row"] for r in json.loads(preview.read_text())["rows"]]
            )
            sampling = "first_100_official_preview_nonrandom"
            source = preview
        events = lade_events(raw)
        events.to_parquet(processed / "lade_events.parquet", index=False)
        # Use the provider's event date key as-is. The date strings have no year/offset.
        date_summary = (
            events.groupby(["city", "ds"])
            .agg(
                events=("courier_id", "size"),
                couriers=("courier_id", "nunique"),
                distinct_delivery_gps_timestamps=("delivery_gps_time", "nunique"),
            )
            .reset_index()
        )
        date_summary["sample_scope"] = sampling
        date_summary["time_basis"] = (
            "provider_ds_and_local_strings; year=2022 per official documentation, timezone unverified"
        )
        save_table(
            date_summary, tables / "public_lade_event_summary.csv", "public_observed"
        )
        repeated = int(
            events.duplicated(
                [
                    "courier_id",
                    "delivery_gps_time",
                    "delivery_gps_lat",
                    "delivery_gps_lng",
                ]
            ).sum()
        )
        valid = events.latitude.between(-90, 90) & events.longitude.between(-180, 180)
        missing = (
            events[["delivery_gps_time", "latitude", "longitude"]].isna().any(axis=1)
        )
        summary["lade"] = {
            "status": "analyzed",
            "rows": len(events),
            "couriers": int(events.courier_id.nunique()),
            "cities": events.city.unique().tolist(),
            "provider_date_key_range": [int(events.ds.min()), int(events.ds.max())],
            "distinct_recorded_days": int(events.ds.nunique()),
            "sample_scope": sampling,
            "duplicate_event_nearest_gps": repeated,
            "invalid_coordinates": int((~valid).sum()),
            "missing_delivery_gps_fields": int(missing.sum()),
            "source_sha256": sha256(source),
            "observation_type": "public_observed",
            "unit": "courier_delivery_event_nearest_gps",
            "continuous_vehicle_gps": False,
            "vehicle_type_known": False,
            "crs_timezone_anonymization": "paper section 3.1 states perturbed coordinates, accuracy limited to 10m; datum/timezone unconfirmed; no metric spatial fusion",
            "duration_rule": "accept_to_delivery_is_not_stationary_dwell",
        }
        if sampling == "full_jilin_partition":
            from .event_study import lade_event_study

            summary["lade"]["event_selection_study"] = lade_event_study(events, output)
    else:
        summary["lade"] = {"status": "not_acquired"}
    osm = root / "osm_seoul_map.osm"
    if osm.exists():
        points = osm_xml_points(osm)
        points.to_parquet(processed / "osm_seoul_amenities.parquet", index=False)
        categories = (
            points.groupby("amenity").size().rename("mapped_nodes").reset_index()
        )
        categories["source"] = "© OpenStreetMap contributors"
        categories["license"] = "ODbL-1.0"
        categories["coverage"] = (
            "nodes in specified bbox; not complete all-geometry POI inventory"
        )
        save_table(
            categories, tables / "public_osm_amenity_summary.csv", "public_observed"
        )
        spatial = Grid().project(points)
        cells = spatial.groupby("grid_id").size().rename("poi_nodes").reset_index()
        cells = cells.merge(
            Grid().cells(cells.grid_id).drop(columns="polygon"), on="grid_id"
        )
        cells["source"] = "© OpenStreetMap contributors"
        cells["license"] = "ODbL-1.0"
        save_table(cells, tables / "public_osm_grid_counts.csv", "public_observed")
        summary["osm"] = {
            "status": "analyzed",
            "amenity_nodes": len(points),
            "categories": len(categories),
            "occupied_200m_cells": len(cells),
            "bbox": [126.975, 37.563, 126.982, 37.568],
            "source_sha256": sha256(osm),
            "observation_type": "public_observed",
            "unit": "mapped_amenity_nodes",
            "source": "© OpenStreetMap contributors",
            "license": "ODbL-1.0",
            "period": "current API snapshot; edit timestamps are not observation validity",
            "integration": "spatial-only; not joined with synthetic GPS or foreign historical events",
        }
    else:
        summary["osm"] = {"status": "not_acquired"}
    write_json(output / "runs/public_summary.json", summary)
    return summary
