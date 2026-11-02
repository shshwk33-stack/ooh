#!/usr/bin/env python3
"""Export verified Phase 1 artifacts to a self-contained, read-only UI bundle.

The boundary is historical public geometry. Vehicle samples are SYNTHETIC.
No mobility/spatial/value scores, visits, stops, or exposure are inferred.
"""
import argparse
import csv
import hashlib
import io
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from pyproj import Transformer
from shapely import wkt
from shapely.geometry import Point, shape

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / 'docs/research/results'
SEOUL = ZoneInfo('Asia/Seoul')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def load_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def verified_run(folder):
    directory = RESULTS / folder
    manifest = load_json(directory / 'run_manifest.json')
    for filename, expected in manifest['outputs'].items():
        if Path(filename).name != filename:
            raise ValueError('Manifest artifact path must be a filename')
        raw = (directory / filename).read_bytes()
        if digest(raw) != expected:
            raise ValueError(f'Artifact hash mismatch: {folder}/{filename}')
    quality = load_json(directory / 'quality_report.json')
    if quality['status'] != 'passed' or quality.get('errors'):
        raise ValueError(f'Input quality has not passed: {folder}')
    return directory, manifest, quality


def verify_original(manifest, raw_path, metadata_path, gps=False):
    raw_hash = manifest['input_sha256'] if gps else manifest['source']['sha256']
    if digest(Path(raw_path).read_bytes()) != raw_hash:
        raise ValueError(f'Original source hash mismatch: {raw_path}')
    if digest(Path(metadata_path).read_bytes()) != manifest['metadata_sha256']:
        raise ValueError(f'Original metadata hash mismatch: {metadata_path}')


def polygons(geometry):
    parts = [geometry] if geometry.geom_type == 'Polygon' else list(geometry.geoms)
    return [[[list(point) for point in part.exterior.coords],
             *[[list(point) for point in ring.coords] for ring in part.interiors]]
            for part in parts]


def metric_features(directory):
    records = []
    with (directory / 'mapo.projected.csv').open(encoding='utf-8', newline='') as stream:
        for row in csv.DictReader(stream):
            if row['crs'] != 'EPSG:5179':
                raise ValueError('Projected artifact requires EPSG:5179')
            geometry = wkt.loads(row['geometry_wkt'])
            if geometry.is_empty or not geometry.is_valid:
                raise ValueError('Invalid projected geometry')
            label = geometry.representative_point()
            records.append({'code': row['code'], 'name': row['name'],
                            'polygons': polygons(geometry),
                            'label': [label.x, label.y],
                            'areaM2': float(row['area_m2']),
                            'perimeterM': float(row['perimeter_m'])})
    return sorted(records, key=lambda item: item['code'])


def spatial_match(point, features):
    """All boundary-inclusive matches; never silently pick a boundary-side unit."""
    return sorted(code for code, geometry in features if geometry.covers(point))


def build_bundle():
    district_dir, district_manifest, district_quality = verified_run('mapo-district')
    dongs_dir, dongs_manifest, dongs_quality = verified_run('mapo-dongs')
    gps_dir, gps_manifest, gps_quality = verified_run('synthetic-gps-validation')
    for manifest in (district_manifest, dongs_manifest):
        if (manifest['source']['kind'] != 'PUBLIC_AGGREGATE'
                or manifest['source']['reference_year'] != 2013
                or manifest.get('geometry_only') is not True
                or manifest.get('analysis_scores_generated') is not False
                or manifest.get('bootstrap_performed') is not False):
            raise ValueError('Boundary provenance/scope mismatch')
    if gps_manifest['source_kind'] != 'SYNTHETIC':
        raise ValueError('This packaged scenario must remain SYNTHETIC')
    verify_original(district_manifest, ROOT / 'public/data/seoul-districts-2013.geojson',
                    ROOT / 'research_data/sources/seoul-districts-2013.metadata.json')
    verify_original(dongs_manifest, ROOT / 'research_data/raw/seoul-submunicipalities-2013.geojson',
                    ROOT / 'research_data/sources/seoul-submunicipalities-2013.metadata.json')
    fixture = ROOT / 'research_data/synthetic/mapo-gps-seed42'
    verify_original(gps_manifest, fixture / 'mapo_synthetic_gps.csv',
                    fixture / 'mapo_synthetic_gps.metadata.json', gps=True)
    district = load_json(district_dir / 'mapo.geojson')
    dongs = load_json(dongs_dir / 'mapo.geojson')
    if len(district['features']) != 1 or len(dongs['features']) != 16:
        raise ValueError('Unexpected administrative feature selection')
    geometries = [(f['properties']['code'], shape(f['geometry'])) for f in dongs['features']]
    if any(not geometry.is_valid for _, geometry in geometries):
        raise ValueError('Invalid geographic boundary')
    forward = Transformer.from_crs('EPSG:4326', 'EPSG:5179', always_xy=True)
    positions = []
    with (gps_dir / 'validated_positions.csv').open(encoding='utf-8', newline='') as stream:
        for index, row in enumerate(csv.DictReader(stream)):
            if row.get('data_type') != 'SYNTHETIC':
                raise ValueError('Vehicle row classification mismatch')
            lon, lat = float(row['longitude']), float(row['latitude'])
            x, y = forward.transform(lon, lat, errcheck=True)
            local = datetime.fromisoformat(row['timestamp'].replace('Z', '+00:00')).astimezone(SEOUL)
            codes = spatial_match(Point(lon, lat), geometries)
            positions.append({'id': f'GPS-{index+1:04d}', 'vehicleId': row['vehicle_id'],
                              'timestamp': row['timestamp'], 'localTimestamp': local.isoformat(),
                              'day': local.date().isoformat(), 'hour': local.hour,
                              'longitude': lon, 'latitude': lat, 'x': x, 'y': y,
                              'dongCodes': codes, 'dongCode': codes[0] if len(codes) == 1 else None,
                              'kind': 'SYNTHETIC'})
    metric_district, metric_dongs = metric_features(district_dir), metric_features(dongs_dir)
    flat = [p for unit in metric_district for polygon in unit['polygons'] for ring in polygon for p in ring]
    bounds = [min(p[0] for p in flat), min(p[1] for p in flat),
              max(p[0] for p in flat), max(p[1] for p in flat)]
    source = dongs_manifest['source']
    bundle = {
        'schemaVersion': '1.0', 'bundleVersion': 'phase1-dashboard-1.0.0',
        'district': district, 'dongs': dongs,
        'projected': {'district': metric_district, 'dongs': metric_dongs,
                      'bounds': bounds, 'crs': 'EPSG:5179'},
        'gps': {'kind': 'SYNTHETIC', 'positions': positions,
                'vehicles': sorted({p['vehicleId'] for p in positions}),
                'days': sorted({p['day'] for p in positions}),
                'period': gps_manifest['period'], 'seed': 42, 'roadConstrained': False,
                'join': {'method': 'Shapely covers; boundary-inclusive; all matches retained',
                         'unmatched': sum(not p['dongCodes'] for p in positions),
                         'ambiguous': sum(len(p['dongCodes']) > 1 for p in positions)}},
        'quality': {'district': district_quality, 'dongs': dongs_quality, 'gps': gps_quality},
        'manifests': {'district': district_manifest, 'dongs': dongs_manifest, 'gps': gps_manifest},
        'source': {'boundaryYear': 2013, 'boundaryKind': 'PUBLIC_AGGREGATE',
                   'gpsKind': 'SYNTHETIC', 'boundarySourceName': source['name'],
                   'upstreamCommit': source['upstream_commit'], 'url': source['url'],
                   'license': source['license'],
                   'redistributorLicense': source['redistributor_license_declaration'],
                   'originalAgencyTermsVerified': source['original_agency_terms_verified'],
                   'inputCrs': 'EPSG:4326', 'metricCrs': 'EPSG:5179',
                   'gpsDateNote': '2024-05-01..03 are artificial scenario dates, not observation dates'},
        'stats': {'unitCount': len(metric_dongs), 'positionCount': len(positions),
                  'vehicleCount': len({p['vehicleId'] for p in positions}),
                  'dayCount': len({p['day'] for p in positions}),
                  'areaM2': sum(unit['areaM2'] for unit in metric_dongs)},
        'scope': {'observedGpsAvailable': False, 'scoresComputed': False,
                  'bootstrapPerformed': False, 'roadNetworkAvailable': False},
        'provenance': {'outputKind': 'DERIVED', 'exporterVersion': '1.0.0',
                       'boundaryRunIds': [district_manifest['run_id'], dongs_manifest['run_id']],
                       'gpsRunId': gps_manifest['run_id'],
                       'originalFilesAndArtifactHashesVerified': True}
    }
    return bundle


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'dashboard/src/research-data.json')
    parser.add_argument('--check', action='store_true', help='Verify existing output is reproducible')
    args = parser.parse_args(argv)
    try:
        bundle = build_bundle()
        payload = (json.dumps(bundle, ensure_ascii=False, sort_keys=True,
                              separators=(',', ':'), allow_nan=False) + '\n').encode('utf-8')
        if args.check:
            if args.output.read_bytes() != payload:
                raise ValueError('Dashboard bundle is stale; regenerate from verified artifacts')
        else:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_bytes(payload)
    except (ValueError, KeyError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps({'status': 'verified', 'bytes': len(payload), 'sha256': digest(payload),
                      'units': len(bundle['projected']['dongs']),
                      'positions': len(bundle['gps']['positions'])}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
