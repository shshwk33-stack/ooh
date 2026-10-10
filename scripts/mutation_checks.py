"""Small declared scientific mutation audit in disposable source copies.

Mutants compile before tests, and collection/import failures never count as kills.
This is a targeted audit, not a whole-program mutation-coverage percentage.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = [
    (
        "timestamp_assumes_nanoseconds",
        "stops.py",
        "(g.timestamp - g.timestamp.iloc[0]).dt.total_seconds().to_numpy()",
        "g.timestamp.astype('int64').to_numpy() / 1e9",
        "test_external_parquet_timestamp_units",
    ),
    (
        "spike_retained",
        "quality.py",
        "d.drop(index=spikes)",
        "d.drop(index=[])",
        "test_isolated_spike_does_not_duplicate_visit",
    ),
    (
        "bootstrap_without_replacement",
        "experiments.py",
        "rng.choice(vehicles, len(vehicles), replace=True)",
        "rng.choice(vehicles, len(vehicles), replace=False)",
        "test_cluster_resampling_really_replaces_and_changes_selection",
    ),
    (
        "placebo_identity",
        "experiments.py",
        "rng.permutation(len(f))",
        "np.arange(len(f))",
        "test_placebo_really_moves_joint_mobility_vectors",
    ),
    (
        "holdout_refits_test",
        "experiments.py",
        "score(b, alpha=analysis.mobility_weight, normalizer=norm)",
        "score(b, alpha=analysis.mobility_weight, normalizer=None)",
        "test_holdout_reuses_frozen_training_normalizer",
    ),
    (
        "reversed_static_weights",
        "scoring.py",
        "0.7 * z.population + 0.3 * z.poi_count",
        "0.3 * z.population + 0.7 * z.poi_count",
        "test_static_weight_direction_and_rank",
    ),
    (
        "rank_ascending",
        "scoring.py",
        'rank(method="average", ascending=False)',
        'rank(method="average", ascending=True)',
        "test_static_weight_direction_and_rank",
    ),
    (
        "utc_hour_boundaries",
        "features.py",
        "return timestamp + pd.Timedelta(seconds=remaining)",
        'return timestamp.floor("h") + pd.Timedelta(hours=1)',
        "test_local_half_hour_boundary_and_visit_not_duplicated",
    ),
    (
        "looser_iou_threshold",
        "stops.py",
        "iou_threshold=0.5",
        "iou_threshold=0.49",
        "test_matching_iou_threshold_is_exact_not_tunable_after_result",
    ),
    (
        "robustness_self_comparison",
        "experiments.py",
        "base.scores, a.scores",
        "a.scores, a.scores",
        "test_robustness_uses_distinct_noiseless_reference",
    ),
]


def run():
    results = []
    with tempfile.TemporaryDirectory(prefix="transit-ooh-mutants-") as tmp:
        work = Path(tmp)
        shutil.copytree(
            ROOT / "src", work / "src", ignore=shutil.ignore_patterns("__pycache__")
        )
        env = dict(os.environ, PYTHONPATH=str(work / "src"))
        baseline_cmd = [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_revision.py",
            "-q",
            "--tb=short",
        ]
        baseline = subprocess.run(
            baseline_cmd,
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if baseline.returncode:
            raise RuntimeError("Mutation baseline failed: " + baseline.stdout[-3000:])
        for name, filename, old, new, test in CASES:
            p = work / "src/transit_ooh" / filename
            original = p.read_text()
            if old not in original:
                raise RuntimeError(f"Mutation pattern not found: {name}")
            mutant = original.replace(old, new)
            compile(mutant, str(p), "exec")
            p.write_text(mutant)
            for cache in (work / "src").rglob("__pycache__"):
                shutil.rmtree(cache)
            xml = work / "result.xml"
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "tests/test_revision.py::" + test,
                    "-q",
                    "--tb=short",
                    "--junitxml=" + str(xml),
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            suite = ET.parse(xml).getroot().find("testsuite")
            failed, errors = int(suite.attrib["failures"]), int(suite.attrib["errors"])
            status = (
                "killed"
                if failed > 0 and errors == 0
                else (
                    "survived"
                    if result.returncode == 0
                    else "invalid_or_infrastructure_error"
                )
            )
            results.append(
                {
                    "name": name,
                    "test": test,
                    "status": status,
                    "failures": failed,
                    "errors": errors,
                    "exit_code": result.returncode,
                }
            )
            print(name, status, flush=True)
            p.write_text(original)
    report = {
        "scope": "10 explicitly declared scientific mutations, not exhaustive code coverage",
        "baseline": "passed",
        "mutants": results,
        "killed": sum(r["status"] == "killed" for r in results),
        "count": len(results),
    }
    (ROOT / "reports/runs/mutation_checks.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    if report["killed"] != len(results):
        raise SystemExit(1)


if __name__ == "__main__":
    run()
