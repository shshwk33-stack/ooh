"""Command line entry point; validation failures exit with status 2."""

import argparse
import json
import sys

from . import PipelineError
from .boundary import run_pipeline


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Validate public administrative boundaries and derive Mapo geometry outputs."
    )
    parser.add_argument("--input", required=True, help="Original EPSG:4326 GeoJSON")
    parser.add_argument("--metadata", required=True, help="Explicit provenance/CRS JSON contract")
    parser.add_argument("--output", required=True, help="New or empty output directory")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--region-code", help="Exact administrative region code (default: 11140)")
    selection.add_argument("--region-prefix", help="Select all administrative codes with this prefix")
    args = parser.parse_args(argv)
    try:
        manifest = run_pipeline(args.input, args.metadata, args.output,
                                region_code=args.region_code, region_prefix=args.region_prefix)
    except PipelineError as exc:
        print(json.dumps({"status": "failed", **exc.issue()}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps({"status": "passed", "run_id": manifest["run_id"],
                      "output": args.output, "geometry_only": True}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
