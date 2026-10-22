"""Bundle the current code, tracked results and presentations without raw inputs."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "deliverables/Transit_OOH_Full_Code_and_Results.zip"
ROOT_FILES = {
    "README.md",
    "CODE_PACKAGE_GUIDE.md",
    "pyproject.toml",
    "uv.lock",
    ".python-version",
    ".env.example",
    ".gitignore",
    ".gitattributes",
}
FOLDERS = {
    "src",
    "app",
    "tests",
    "scripts",
    "configs",
    "examples",
    "docs",
    "tools",
    "reports",
    ".github",
    "deliverables",
}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
    names = {name.decode() for name in tracked.split(b"\0") if name}
    names.update({"CODE_PACKAGE_GUIDE.md", "scripts/package_full_code.py"})
    paths = []
    for relative in sorted(names):
        path = ROOT / relative
        parts = Path(relative).parts
        allowed = (
            relative in ROOT_FILES
            or parts[0] in FOLDERS
            or (parts[0] == "reference" and path.suffix == ".ipynb")
            or relative.startswith("reference/reviews/")
        )
        if not allowed or path.suffix == ".zip":
            continue
        if relative.startswith("deliverables/") and len(parts) == 2:
            # Old package receipts without their ZIPs are not part of this bundle.
            continue
        if any(x in parts for x in ("__pycache__", "private", ".venv", ".cache")):
            raise ValueError("Private or generated cache path in tracked files")
        if path.is_symlink() or not path.is_file():
            raise ValueError("Expected a regular tracked file: " + relative)
        paths.append(path)
    for name in ("full_code_package_tests.xml", "full_code_package_validation.json"):
        path = ROOT / "reports/runs" / name
        if path.is_file() and path not in paths:
            paths.append(path)
    paths = sorted(set(paths))
    relative_names = {p.relative_to(ROOT).as_posix() for p in paths}
    required = {
        "src/transit_ooh/public_decision.py",
        "app/streamlit_app.py",
        "scripts/check_public_portfolios.py",
        "reports/public_decision/summary.json",
        "reports/public_decision/tables/candidate_features.csv",
        "deliverables/competition2026_pmstyle/Transit_OOH_PMstyle_Anonymous.pptx",
        "deliverables/competition2026_pmstyle/Transit_OOH_PMstyle_Anonymous.pdf",
        "deliverables/competition2026_pmstyle/requirements-presentation.txt",
        "CODE_PACKAGE_GUIDE.md",
        "uv.lock",
    }
    if not required <= relative_names:
        raise ValueError("Missing package inputs: " + str(required - relative_names))
    if sum(p.suffix == ".ipynb" for p in paths) != 1:
        raise ValueError("Original synthetic PoC regression notebook is required")
    report = ROOT / "reports/public_decision"
    summary = json.loads((report / "summary.json").read_text())
    for relative, expected in summary["artifacts_sha256"].items():
        path = (report / relative).resolve()
        if (
            not path.is_relative_to(report.resolve())
            or sha256(path) != expected
            or path.relative_to(ROOT).as_posix() not in relative_names
        ):
            raise ValueError("Missing or changed acquired-study artifact: " + relative)
    records = {
        p.relative_to(ROOT).as_posix(): {
            "bytes": p.stat().st_size,
            "sha256": sha256(p),
        }
        for p in paths
    }
    manifest = {
        "created_at_utc": datetime.now(UTC).isoformat(),
        "research_and_presentation_base_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "source_report_sha256": sha256(report / "summary.json"),
        "scope": "Full code, tests, locked dependencies, aggregate results and presentations",
        "excluded": [
            "provider raw inputs and individual location records",
            "credentials and virtual environments",
            "nested ZIPs and private reference presentations",
        ],
        "files": records,
    }
    with ZipFile(OUTPUT, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for path in paths:
            archive.write(path, path.relative_to(ROOT).as_posix())
        archive.writestr(
            "PACKAGE_MANIFEST.json",
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        )
        archive.writestr(
            "먼저읽어주세요.txt",
            "Transit OOH 전체 코드·결과 패키지\n\n"
            "실행 방법: CODE_PACKAGE_GUIDE.md\n"
            "코드: src/ 및 app/\n"
            "현재 실제 결과: reports/public_decision/\n"
            "최신 PPT·PDF·대본: deliverables/competition2026_pmstyle/\n\n"
            "기본 공개자료 화면은 제공된 집계표로 실행되며 API 키가 필요하지 않습니다.\n"
            "기관 원본부터 다시 처리하거나 다른 실제 자료 화면을 열려면 별도 입력이 필요합니다.\n"
            "이 ZIP은 코드·검수용이며 익명 발표 제출본과 구분합니다.\n",
        )
    with ZipFile(OUTPUT) as archive:
        if archive.testzip() is not None:
            raise ValueError("Package CRC failed")
        for relative, record in records.items():
            if hashlib.sha256(archive.read(relative)).hexdigest() != record["sha256"]:
                raise ValueError("Package file hash differs: " + relative)
    receipt = {
        "file": OUTPUT.name,
        "bytes": OUTPUT.stat().st_size,
        "sha256": sha256(OUTPUT),
        "packaged_files_verified": len(records),
        "crc_verified": True,
        "acquired_study_artifacts_verified": len(summary["artifacts_sha256"]),
    }
    OUTPUT.with_suffix(".validation.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
