"""Command-line workflow. Acquisition failures never turn into silent synthetic data."""

import argparse
import json
import sys
from pathlib import Path

from .io import load_config, provenance, read_table, save_table


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Transit OOH reproducible research; observed and synthetic studies are separate"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    research = sub.add_parser("research")
    research.add_argument("--config", default="configs/default.yaml")
    research.add_argument("--output", default="reports")
    research.add_argument("--quick", action="store_true")
    viewt = sub.add_parser("viewt")
    viewt.add_argument("--input", help="Canonical XLSX or CSV directory")
    viewt.add_argument("--demo", action="store_true")
    viewt.add_argument("--district", default="마포구")
    viewt.add_argument("--weight", type=float, default=0.5)
    viewt.add_argument("--hours", type=int, nargs="+")
    viewt.add_argument("--replicates", type=int, default=200)
    viewt.add_argument("--output", default="reports/viewt")
    sub.add_parser("fetch-public")
    sub.add_parser("public-analysis")
    for name in ["validate", "analyze"]:
        p = sub.add_parser(name)
        p.add_argument("--gps", required=True)
        p.add_argument("--metadata")
        p.add_argument("--config", default="configs/default.yaml")
        p.add_argument("--output", default="data/processed/imported")
        p.add_argument("--context")
        p.add_argument("--context-metadata")
    args = parser.parse_args(argv)
    try:
        if args.command == "research":
            from .research import run_research

            run_research(args.config, args.output, args.quick)
        elif args.command == "viewt":
            from .viewt import demo_bundle, read_bundle
            from .viewt_report import export_study

            if bool(args.input) == args.demo:
                raise ValueError("Choose exactly one: --input or --demo")
            bundle = (
                demo_bundle(args.district) if args.demo else read_bundle(args.input)
            )
            manifest = export_study(
                bundle, args.output, args.weight, args.hours, args.replicates
            )
            print(json.dumps(manifest, ensure_ascii=False, indent=2))
        elif args.command == "fetch-public":
            from .sources import acquire_public

            r = acquire_public()
            print(json.dumps(r, indent=2))
            return int(any(x["status"] == "failed" for x in r))
        elif args.command == "public-analysis":
            from .public_analysis import analyze_public

            print(json.dumps(analyze_public(), indent=2))
        else:
            from .pipeline import analyze
            from .quality import normalize_gps

            d = read_table(args.gps)
            cfg = load_config(args.config)
            if args.metadata:
                meta = json.loads(Path(args.metadata).read_text())
                if meta.get("crs") != "EPSG:4326":
                    raise ValueError("Convert input CRS explicitly to EPSG:4326")
                d = provenance(
                    d,
                    meta["source"],
                    meta["observation_type"],
                    meta["observation_unit"],
                )
                cfg["timezone"] = meta["timezone"]
            out = Path(args.output)
            out.mkdir(parents=True, exist_ok=True)
            if args.command == "validate":
                clean, q = normalize_gps(
                    d,
                    **{
                        k: cfg[k]
                        for k in [
                            "timezone",
                            "max_gap_seconds",
                            "max_speed_kmh",
                            "max_accuracy_m",
                        ]
                    },
                )
                save_table(q, out / "quality.csv")
                print(q.to_string(index=False))
                return int(clean.empty)
            if bool(args.context) != bool(args.context_metadata):
                raise ValueError("Provide both context and context metadata")
            context = read_table(args.context) if args.context else None
            meta = (
                json.loads(Path(args.context_metadata).read_text())
                if args.context_metadata
                else None
            )
            if context is not None and meta is None:
                raise ValueError("Context metadata is required")
            a = analyze(d, cfg, context, meta)
            save_table(a.scores.drop(columns="polygon"), out / "scores.csv")
            save_table(a.quality, out / "quality.csv")
            save_table(a.stops, out / "stops.csv")
            print(
                f"Analyzed {len(a.gps)} fixes; {len(a.stops)} episodes. Output: {out}"
            )
        return 0
    except (ValueError, KeyError, OSError, RuntimeError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
