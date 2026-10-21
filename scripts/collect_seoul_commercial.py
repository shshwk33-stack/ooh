"""Download official Seoul historical commercial files with bounded HTTPS I/O.

The datasets are current revised historical releases, not an as-of-2024 archive.
No API token is required for this provider download endpoint.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zipfile import ZipFile

ENDPOINT = (
    "https://datafile.seoul.go.kr/bigfile/iot/inf/nio_download.do?&useCache=false"
)
FILES = {"stores_2024": ("OA-22172", "6"), "sales_2025": ("OA-22175", "7")}
MAX_DOWNLOAD = 80_000_000


def acquire(name: str, destination: Path, protocol: Path | None = None):
    dataset, sequence = FILES[name]
    path = destination / f"{name}.zip"
    receipt = destination / f"{name}.provenance.json"
    protocol_sha = None
    if name == "sales_2025":
        if protocol is None or not protocol.is_file():
            raise ValueError(
                "Write the analysis protocol before downloading 2025 outcomes"
            )
        protocol_sha = hashlib.sha256(protocol.read_bytes()).hexdigest()
    if path.exists() and receipt.exists():
        meta = json.loads(receipt.read_text())
        if hashlib.sha256(path.read_bytes()).hexdigest() != meta["sha256"]:
            raise ValueError(
                "Changed cached source; preserve and review it before reacquisition"
            )
        return {"name": name, "status": "verified_cache", "sha256": meta["sha256"]}
    form = {"infId": dataset, "seqNo": "", "seq": sequence, "infSeq": "3"}
    request = Request(ENDPOINT, data=urlencode(form).encode("ascii"), method="POST")
    with urlopen(request, timeout=60) as response:
        if int(response.headers.get("Content-Length", 0)) > MAX_DOWNLOAD:
            raise ValueError("Provider download exceeds 80 MB")
        body = bytearray()
        while chunk := response.read(65536):
            body.extend(chunk)
            if len(body) > MAX_DOWNLOAD:
                raise ValueError("Provider download exceeds 80 MB")
    with ZipFile(io.BytesIO(body)) as archive:
        if archive.testzip() is not None:
            raise ValueError("Provider ZIP failed CRC validation")
    if path.exists() and path.read_bytes() != bytes(body):
        raise ValueError(
            "Unreceipted existing source differs; preserve it before proceeding"
        )
    destination.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    meta = {
        "url": ENDPOINT,
        "method": "POST",
        "form": form,
        "dataset_page": f"https://data.seoul.go.kr/dataList/{dataset}/S/1/datasetView.do",
        "retrieved_at_utc": datetime.now(UTC).isoformat(),
        "bytes": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
        "tls_verified": True,
        "license": "Korea Open Government License Type 1; attribution required",
        "vintage": "current revised historical release; not historical as-of data",
    }
    if protocol_sha:
        meta["protocol_before_download_sha256"] = protocol_sha
        meta["prior_preliminary_outcomes_known"] = True
        meta["evaluation_status"] = (
            "retrospective reproduction; not unseen prospective holdout"
        )
    receipt.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
    return {
        "name": name,
        "status": "downloaded",
        "bytes": len(body),
        "sha256": meta["sha256"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="data/raw/seoul_commercial")
    parser.add_argument("--datasets", nargs="+", choices=FILES, default=list(FILES))
    parser.add_argument("--protocol", default="docs/PUBLIC_DATA_RESEARCH_PROTOCOL.md")
    args = parser.parse_args()
    destination = Path(args.output)
    for name in args.datasets:
        print(
            json.dumps(
                acquire(name, destination, Path(args.protocol)), ensure_ascii=False
            )
        )


if __name__ == "__main__":
    main()
