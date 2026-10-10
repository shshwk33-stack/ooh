"""Audit preserved notebook without modifying it. Execute cells in a fresh namespace."""

from pathlib import Path
import contextlib
import io
import json
import hashlib

ROOT = Path(__file__).resolve().parents[1]


def run(seed=42):
    path = next((ROOT / "reference").glob("*.ipynb"))
    nb = json.loads(path.read_text())
    ns = {}
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        for i, c in enumerate(nb["cells"]):
            if c["cell_type"] != "code" or i > 22:
                continue
            code = "".join(c["source"])
            if i == 2:
                code = code.replace("np.random.seed(42)", f"np.random.seed({seed})")
            exec(compile(code, f"original-cell-{i}", "exec"), ns)
            ns["display"] = lambda *args, **kwargs: None
    gps = ns["gps"]
    stops = ns["valid_stops"]
    result = ns["comparison"]
    # Scheduled stop durations from original generator calls; no inference from detector.
    scheduled = sum([15, 20, 20, 10, 15, 20, 15, 10, 10, 15, 15])
    return {
        "seed": seed,
        "vehicles": int(gps.vehicle_id.nunique()),
        "gps_rows": len(gps),
        "occupied_grids": int(gps.grid_id.nunique()),
        "candidate_grids": len(result),
        "stops": len(stops),
        "generated_stop_minutes": scheduled,
        "estimated_stop_minutes": float(stops.dwell_minutes.sum()),
        "move_label_stop_candidates": int(
            ((gps.scenario_state == "MOVE") & gps.stop_candidate).sum()
        ),
        "top_grid": result.sort_values("proposed_rank").iloc[0].grid_id,
        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }, ns


if __name__ == "__main__":
    for folder in ["reports/tables", "reports/runs", "archive/audit"]:
        (ROOT / folder).mkdir(parents=True, exist_ok=True)
    rows = []
    for seed in [11, 42, 73, 101, 202]:
        row, ns = run(seed)
        rows.append(row)
        if seed == 42:
            ns["comparison"].assign(
                observation_type="synthetic", analysis_variant="legacy_original"
            ).to_csv(ROOT / "reports/tables/legacy_comparison.csv", index=False)
            ns["gps"].to_csv(ROOT / "archive/audit/legacy_gps.csv", index=False)
    (ROOT / "reports/runs/legacy_audit.json").write_text(json.dumps(rows, indent=2))
    print(json.dumps(rows, indent=2))
