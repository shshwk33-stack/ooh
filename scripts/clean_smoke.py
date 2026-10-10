"""Reinstall locked runtime in a disposable directory, with no raw data or Git."""

import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
started = time.monotonic()
results = []
with tempfile.TemporaryDirectory(prefix="transit-ooh-smoke-") as tmp:
    work = Path(tmp)
    for name in ["src", "configs", "app", "scripts"]:
        shutil.copytree(
            ROOT / name, work / name, ignore=shutil.ignore_patterns("__pycache__")
        )
    for name in ["pyproject.toml", "uv.lock", ".python-version"]:
        shutil.copy2(ROOT / name, work / name)
    environment = os.environ.copy()
    environment.update(
        UV_CACHE_DIR=str(ROOT / ".cache/uv"),
        XDG_CACHE_HOME=str(work / ".cache"),
        MPLCONFIGDIR=str(work / ".cache/matplotlib"),
    )
    cmds = [
        ["uv", "sync", "--frozen", "--no-dev"],
        [
            str(work / ".venv/bin/python"),
            "-m",
            "transit_ooh.cli",
            "research",
            "--quick",
        ],
        [
            str(work / ".venv/bin/python"),
            "-m",
            "transit_ooh.cli",
            "viewt",
            "--demo",
            "--replicates",
            "10",
        ],
        [
            str(work / ".venv/bin/python"),
            "-c",
            "from streamlit.testing.v1 import AppTest; from pathlib import Path; a=AppTest.from_file(Path('app/streamlit_app.py').resolve(),default_timeout=40).run(); assert not a.exception, [e.message for e in a.exception]; print('fresh-runtime app render passed')",
        ],
    ]
    for cmd in cmds:
        r = subprocess.run(
            cmd,
            cwd=work,
            env=environment,
            text=True,
            capture_output=True,
            timeout=300,
            check=False,
        )
        results.append(
            {
                "command": [s.replace(str(work), "<fresh-workspace>") for s in cmd],
                "exit_code": r.returncode,
                "stdout_tail": r.stdout[-1800:],
                "stderr_tail": r.stderr[-700:],
            }
        )
        if r.returncode:
            (ROOT / "reports/runs/clean_smoke.json").write_text(
                json.dumps({"status": "failed", "commands": results}, indent=2)
            )
            print(r.stdout, r.stderr)
            raise SystemExit(r.returncode)
    latest = json.loads((work / "reports/runs/latest.json").read_text())
    manifest = json.loads((work / latest["manifest"]).read_text())
    assert manifest["quick"] and manifest["sample"]["gps_rows"] > 0
    assert all(x["status"] == "not_acquired" for x in manifest["public_data"].values())
    assert len(list((work / "reports/figures").glob("*.png"))) > 0
    summary = {
        "status": "passed",
        "elapsed_seconds": round(time.monotonic() - started, 2),
        "fresh_virtual_environment": True,
        "original_raw_data_present": False,
        "git_metadata_present": False,
        "public_data": "not_acquired; no silent synthetic replacement",
        "sample": manifest["sample"],
        "executed_experiments": manifest["executed_experiments"],
        "commands": results,
        "disposable_workspace_removed_after_check": True,
    }
    (ROOT / "reports/runs/clean_smoke.json").write_text(json.dumps(summary, indent=2))
print("Clean environment install → analysis → experiments → figures → app: passed")
