"""Replay the verified Mapo 2024 queries after official download authentication."""

import argparse
import getpass
import hashlib
import json
import os
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from transit_ooh.viewt_client import ENDPOINTS, ViewTClient, ViewTNoDataError
from transit_ooh.viewt_population import export_population, normalize_response


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", default="data/raw/viewt_population")
    parser.add_argument("--output", default="data/processed/viewt_population")
    parser.add_argument("--daily-start", help="Optional 2024-12-02 style date")
    parser.add_argument("--daily-end", help="At most 31 calendar days; weekdays only")
    parser.add_argument(
        "--skip-empty-daily",
        action="store_true",
        help="Record an empty daily result as missing and continue; never skip permission errors",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Replace existing responses; otherwise validate and reuse",
    )
    args = parser.parse_args()
    daily_dates = []
    if bool(args.daily_start) != bool(args.daily_end):
        raise ValueError("Provide both daily date bounds")
    if args.daily_start:
        start, end = (
            date.fromisoformat(args.daily_start),
            date.fromisoformat(args.daily_end),
        )
        if start.year != 2024 or end.year != 2024 or not 0 <= (end - start).days < 31:
            raise ValueError(
                "Daily acquisition requires a 1–31-day interval within 2024"
            )
        daily_dates = [start + timedelta(days=i) for i in range((end - start).days + 1)]
        daily_dates = [d for d in daily_dates if d.weekday() < 5]
    raw_directory = Path(args.raw)
    raw_directory.mkdir(parents=True, exist_ok=True)
    client = ViewTClient()
    token = os.environ.get("VIEWT_DOWNLOAD_TOKEN") or getpass.getpass(
        "View-T download token (hidden): "
    )
    client.authenticate(token)
    del token
    print("Official View-T token accepted", flush=True)
    audit = {
        "authenticated": True,
        "started_at": datetime.now(UTC).isoformat(),
        "requests": [],
    }

    def acquire(stem, kind, params):
        output = raw_directory / (stem + ".json")
        request_path = raw_directory / (stem + ".request.json")
        reused = output.is_file() and request_path.is_file() and not args.refresh
        if reused:
            if json.loads(request_path.read_text()) != params:
                raise ValueError(
                    "Saved request differs; choose another directory or --refresh"
                )
            raw = output.read_bytes()
        else:
            time.sleep(1)
            try:
                raw = client.fetch(kind, params)
            except ViewTNoDataError as exc:
                diagnostics = raw_directory / "diagnostics"
                diagnostics.mkdir(exist_ok=True)
                (diagnostics / (stem + ".json")).write_bytes(exc.raw)
                (diagnostics / (stem + ".request.json")).write_text(
                    json.dumps(params, indent=2)
                )
                raise
        if kind in {"inflow", "od"}:
            normalize_response(json.loads(raw), params, kind)
        if not reused:
            request_path.write_text(json.dumps(params, ensure_ascii=False, indent=2))
            output.write_bytes(raw)
        audit["requests"].append(
            {
                "file": output.name,
                "endpoint": ENDPOINTS[kind],
                "reused": reused,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "bytes": len(raw),
            }
        )
        (raw_directory / "acquisition.json").write_text(
            json.dumps(audit, ensure_ascii=False, indent=2)
        )
        print(
            f"{stem}: {'reused' if reused else 'acquired'} ({len(raw)} bytes)",
            flush=True,
        )
        return json.loads(raw)

    names = acquire("zone_names_2024", "names", {"year": 2024})["shpMap"]
    dong_codes = sorted(
        k for k, v in names.items() if v.startswith("서울특별시 마포구 ")
    )
    if len(dong_codes) != 16 or names.get("11140000") != "서울특별시 마포구":
        raise ValueError("Official Mapo code lookup differs; review before proceeding")
    days = [date(2024, 1, 1) + timedelta(days=i) for i in range(366)]
    days = [d.strftime("%Y%m%d") for d in days if d.weekday() < 5]
    hours = ",".join(map(str, range(24)))
    base = {
        "url": "/Mobile_InOutMulti_Traffic/",
        "fn_name": "InOutMultiTraffic",
        "year": 2024,
        "trafficType": "In",
        "zoneType": "2",
        "zone": "11140000",
        "subZoneType": "0",
        "subZone": 0,
        "displayResult": "2",
        "dayTerm": ",".join(days),
        "daysCnt": len(days),
        "times": hours + "/" + hours,
        "trips": "11,12,13,14,15,16/11,12,13,14,15,16",
        "sexs": "1,2",
        "ages": ",".join(map(str, range(0, 120, 10))),
    }
    pilot = {
        **base,
        "dayTerm": "20241202,20241203,20241204,20241205,20241206",
        "daysCnt": 5,
    }
    acquire("mapo_inflow_20241202_20241206", "inflow", pilot)
    acquire("mapo_inflow_2024_weekdays", "inflow", base)
    for n, start in enumerate(range(0, 16, 5), 1):
        acquire(
            f"mapo_dong_inflow_2024_weekdays_{n}",
            "inflow",
            {**base, "zoneType": "3", "zone": ",".join(dong_codes[start : start + 5])},
        )
    for stem, params in [
        ("mapo_od_dong_20241202_20241206", pilot),
        ("mapo_od_dong_2024_weekdays", base),
    ]:
        od = {
            k: v
            for k, v in params.items()
            if k not in ["trafficType", "subZoneType", "subZone"]
        }
        od.update(
            url="/Mobile_OD_Traffic",
            fn_name="OD_Traffic",
            displayResult="3",
            LineType="OOD",
            drawlimits=10000,
        )
        acquire(stem, "od", od)
    for day in ["20240102", "20241202"]:
        acquire(
            "mapo_inflow_" + day,
            "inflow",
            {**base, "dayTerm": day + "/" + day, "daysCnt": 1},
        )
    for origin, destination in [
        ("11140740", "11140680"),
        ("11140680", "11140770"),
        ("11140770", "11140740"),
    ]:
        acquire(
            f"vehicle_paths_{origin}_{destination}",
            "vehicle_paths",
            {
                "DPRTR_ZONEID": origin,
                "ARRIVE_ZONEID": destination,
                "YEAR": 2024,
                "WEEKTYPE": 0,
                "TIME": "ALL",
            },
        )
    missing_dates = []
    for day in daily_dates:
        stamp = day.strftime("%Y%m%d")
        for n, start in enumerate(range(0, 16, 5), 1):
            try:
                acquire(
                    f"mapo_dong_inflow_daily_{stamp}_{n}",
                    "inflow",
                    {
                        **base,
                        "zoneType": "3",
                        "zone": ",".join(dong_codes[start : start + 5]),
                        "dayTerm": stamp + "/" + stamp,
                        "daysCnt": 1,
                    },
                )
            except ViewTNoDataError:
                if not args.skip_empty_daily:
                    raise
                missing_dates.append(str(day))
                print(
                    f"{day}: empty provider response; date marked missing", flush=True
                )
                break
    if daily_dates:
        (raw_directory / "daily_coverage.json").write_text(
            json.dumps(
                {
                    "planned_dates": [str(d) for d in daily_dates],
                    "missing_dates": missing_dates,
                },
                indent=2,
            )
        )
    manifest = export_population(raw_directory, args.output)
    print(f"Validated population datasets: {len(manifest['datasets'])}", flush=True)


if __name__ == "__main__":
    main()
