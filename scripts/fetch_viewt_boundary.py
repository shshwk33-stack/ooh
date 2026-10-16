"""Retrieve the official 2024 map layer for Mapo, with provenance and bounded extent."""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import requests
from pyproj import Transformer

from transit_ooh.viewt_boundary import export_boundary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--names", default="data/raw/viewt_population/zone_names_2024.json"
    )
    parser.add_argument("--output", default="data/processed/viewt_boundaries")
    parser.add_argument("--raw", default="data/raw/viewt_boundary_probe")
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    raw = Path(args.raw)
    raw.mkdir(parents=True, exist_ok=True)
    x1, y1 = Transformer.from_crs(4326, 3857, always_xy=True).transform(126.86, 37.53)
    x2, y2 = Transformer.from_crs(4326, 3857, always_xy=True).transform(126.97, 37.61)
    params = {
        "service": "WFS",
        "version": "1.0.0",
        "request": "GetFeature",
        "typeName": "sqlite:zone_emd_2024",
        "outputFormat": "application/json",
        "srsname": "EPSG:4326",
        "bbox": f"{x1},{y1},{x2},{y2},EPSG:3857",
        "maxFeatures": 1000,
    }
    url = "https://viewt.ktdb.go.kr/geoserver/sqlite/ows"
    if args.refresh or not (raw / "response.bin").exists():
        with requests.get(url, params=params, timeout=30, stream=True) as response:
            response.raise_for_status()
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 8 * 1024 * 1024:
                    raise ValueError("Boundary response exceeds 8 MiB")
                chunks.append(chunk)
            content = b"".join(chunks)
        (raw / "response.bin").write_bytes(content)
        request = {
            "source": url,
            "params": params,
            "status": 200,
            "sha256": hashlib.sha256(content).hexdigest(),
            "acquired_at_utc": datetime.now(UTC).isoformat(),
        }
        (raw / "request.json").write_text(json.dumps(request, indent=2))
    content = (raw / "response.bin").read_bytes()
    request = json.loads((raw / "request.json").read_text())
    if (
        request["source"] != url
        or request["params"] != params
        or request["status"] != 200
        or request["sha256"] != hashlib.sha256(content).hexdigest()
    ):
        raise ValueError("Boundary cache request or checksum differs")
    names = Path(args.names).read_bytes()
    result = export_boundary(
        json.loads(content),
        json.loads(names),
        {
            "request": request,
            "names_sha256": hashlib.sha256(names).hexdigest(),
            "layer_basis": "official Expert yearMap V_YEAR=2024; TxMapGlobal.js Zone.Emd='zone_emd_'+V_YEAR",
            "layer_definition_url": "https://viewt.ktdb.go.kr/cong/js/second_map/owner/TxMapGlobal.js",
        },
        args.output,
    )
    print(
        json.dumps(
            {
                "dongs": result["rows"],
                "max_relative_area_difference": result["max_relative_area_difference"],
                "use": result["use"],
            }
        )
    )


if __name__ == "__main__":
    main()
