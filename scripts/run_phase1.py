#!/usr/bin/env python3
"""Run the two real boundary imports and the separately labeled synthetic GPS check."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline import PipelineError
from pipeline.boundary import run_pipeline
from pipeline.gps_input import GPSInputError, run_gps_pipeline


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, help='New or empty results directory')
    args = parser.parse_args(argv)
    output = Path(args.output).resolve()
    # Each child pipeline also protects originals and existing results.
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        parser.error('Output must be a new or empty directory; nothing is overwritten')
    for protected in ('src', 'dashboard', 'public', 'research_data/raw',
                      'research_data/sources', 'research_data/synthetic', 'pipeline'):
        target = ROOT / protected
        if output == target or output in target.parents or target in output.parents:
            parser.error('Output must be separate from source code and input data')
    output.mkdir(parents=True, exist_ok=True)
    try:
        district = run_pipeline(
            ROOT / 'public/data/seoul-districts-2013.geojson',
            ROOT / 'research_data/sources/seoul-districts-2013.metadata.json',
            output / 'mapo-district', region_code='11140')
        dongs = run_pipeline(
            ROOT / 'research_data/raw/seoul-submunicipalities-2013.geojson',
            ROOT / 'research_data/sources/seoul-submunicipalities-2013.metadata.json',
            output / 'mapo-dongs', region_prefix='11140')
        gps_dir = ROOT / 'research_data/synthetic/mapo-gps-seed42'
        gps = run_gps_pipeline(gps_dir / 'mapo_synthetic_gps.csv',
                               gps_dir / 'mapo_synthetic_gps.metadata.json',
                               output / 'synthetic-gps-validation')
    except (PipelineError, GPSInputError, OSError) as exc:
        (output / 'summary.json').write_text(json.dumps({
            'status': 'failed', 'error': str(exc),
            'note': 'Inspect each child quality report. No failed input is replaced.'
        }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(str(exc), file=sys.stderr)
        return 2
    summary = {
        'status': 'passed', 'phase': 1,
        'runs': {
            'mapo-district': {'source_kind': 'PUBLIC_AGGREGATE', 'run_id': district['run_id']},
            'mapo-dongs': {'source_kind': 'PUBLIC_AGGREGATE', 'run_id': dongs['run_id']},
            'synthetic-gps-validation': {'source_kind': 'SYNTHETIC', 'run_id': gps['run_id']}
        },
        'observed_delivery_gps_available': False,
        'model_scores_computed': False,
        'bootstrap_performed': False,
        'dashboard_connected_to_pipeline': False,
        'scope': 'Historical real boundary processing and isolated synthetic GPS input validation'
    }
    (output / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, sort_keys=True,
                                                  indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
