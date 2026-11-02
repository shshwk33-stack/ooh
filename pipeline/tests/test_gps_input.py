import copy
import csv
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

from pipeline.gps_input import GPSInputError, main, run_gps_pipeline, validate_csv
from pipeline import gps_input
from pipeline.scenario import generate


ROOT = Path(__file__).resolve().parents[2]


def fixture(rows=None, kind="OBSERVED_GPS", extra=()):
    rows = rows if rows is not None else [
        {"vehicle_id": "A", "timestamp": "2024-05-01T01:00:00Z", "longitude": "126.9245", "latitude": "37.5572"},
        {"vehicle_id": "A", "timestamp": "2024-05-01T01:01:00Z", "longitude": "126.9246", "latitude": "37.5573"},
    ]
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=["vehicle_id", "timestamp", "longitude", "latitude", *extra], lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    raw = stream.getvalue().encode()
    metadata = {"schema_version": "1.0", "dataset_kind": "vehicle_positions", "source": {"kind": kind, "name": "Validation fixture", "sha256": hashlib.sha256(raw).hexdigest(), "timezone": "UTC", "provenance": "Unit-test input; classification is a test assertion"}, "spatial": {"input_crs": "EPSG:4326", "coordinate_order": "longitude_latitude"}}
    if kind == "SYNTHETIC":
        metadata["generator"] = {"seed": 42, "method": "unit-test fixture"}
    return raw, metadata


class GPSInputTests(unittest.TestCase):
    def test_valid_sort_utc_and_no_score_results(self):
        raw, meta = fixture()
        rows, quality, _ = validate_csv(raw, meta)
        self.assertEqual(quality["status"], "passed")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["longitude"], "126.9245")
        self.assertEqual(rows[0]["data_type"], "OBSERVED_GPS")
        self.assertTrue(any("does not certify" in item for item in quality["warnings"]))

    def test_rejects_missing_column_and_empty_input(self):
        raw, meta = fixture([])
        _, quality, _ = validate_csv(raw, meta)
        self.assertEqual(quality["status"], "failed")
        raw = b"vehicle_id,timestamp,longitude\nA,2024-05-01T00:00:00Z,126\n"
        meta["source"]["sha256"] = hashlib.sha256(raw).hexdigest()
        with self.assertRaisesRegex(GPSInputError, "latitude"):
            validate_csv(raw, meta)

    def test_rejects_nan_range_and_missing(self):
        for value in ("nan", "inf", "181", ""):
            with self.subTest(value=value):
                raw, meta = fixture([{"vehicle_id": "A", "timestamp": "2024-05-01T00:00:00Z", "longitude": value, "latitude": "37.5"}])
                self.assertEqual(validate_csv(raw, meta)[1]["status"], "failed")

    def test_rejects_offsetless_and_timezone_mismatch(self):
        for timestamp in ("2024-05-01T00:00:00", "2024-05-01T00:00:00+09:00"):
            raw, meta = fixture([{"vehicle_id": "A", "timestamp": timestamp, "longitude": "126.9", "latitude": "37.5"}])
            self.assertEqual(validate_csv(raw, meta)[1]["status"], "failed")

    def test_rejects_duplicate_and_conflicting_instant(self):
        for longitude in ("126.9245", "126.9246"):
            raw, meta = fixture([{"vehicle_id": "A", "timestamp": "2024-05-01T00:00:00Z", "longitude": "126.9245", "latitude": "37.5"}, {"vehicle_id": "A", "timestamp": "2024-05-01T00:00:00Z", "longitude": longitude, "latitude": "37.5"}])
            self.assertEqual(validate_csv(raw, meta)[1]["status"], "failed")

    def test_rejects_implausible_inferred_and_recorded_speed(self):
        raw, meta = fixture([{"vehicle_id": "A", "timestamp": "2024-05-01T00:00:00Z", "longitude": "126", "latitude": "37"}, {"vehicle_id": "A", "timestamp": "2024-05-01T00:00:01Z", "longitude": "127", "latitude": "37"}])
        self.assertTrue(any("inferred speed" in error for error in validate_csv(raw, meta)[1]["errors"]))
        raw, meta = fixture([{"vehicle_id": "A", "timestamp": "2024-05-01T00:00:00Z", "longitude": "126", "latitude": "37", "speed_kmh": "-1"}], extra=("speed_kmh",))
        self.assertEqual(validate_csv(raw, meta)[1]["status"], "failed")

    def test_rejects_bad_metadata_hash_and_crs(self):
        raw, meta = fixture()
        for update in ({"kind": "DERIVED"}, {"sha256": "0" * 64}, {"provenance": ""}, {"timezone": "not/a-zone"}):
            candidate = copy.deepcopy(meta)
            candidate["source"].update(update)
            with self.assertRaises(GPSInputError):
                validate_csv(raw, candidate)
        meta["spatial"]["input_crs"] = "EPSG:5179"
        with self.assertRaises(GPSInputError):
            validate_csv(raw, meta)

    def test_synthetic_cannot_be_relabeled_observed(self):
        raw, meta = fixture([{"vehicle_id": "A", "timestamp": "2024-05-01T00:00:00Z", "longitude": "126.9", "latitude": "37.5", "data_type": "SYNTHETIC"}], "SYNTHETIC", ("data_type",))
        self.assertEqual(validate_csv(raw, meta)[1]["status"], "passed")
        meta["source"]["kind"] = "OBSERVED_GPS"
        with self.assertRaises(GPSInputError):
            validate_csv(raw, meta)
        del meta["generator"]
        self.assertEqual(validate_csv(raw, meta)[1]["status"], "failed")

    def test_synthetic_requires_infile_label_and_seed(self):
        raw, meta = fixture(kind="SYNTHETIC")
        with self.assertRaises(GPSInputError):
            validate_csv(raw, meta)
        del meta["generator"]["seed"]
        with self.assertRaises(GPSInputError):
            validate_csv(raw, meta)

    def test_run_reproducibility_and_unchanged_inputs(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            raw, meta = fixture()
            inp, metadata = root / "input.csv", root / "metadata.json"
            inp.write_bytes(raw)
            metadata.write_text(json.dumps(meta))
            first = run_gps_pipeline(inp, metadata, root / "first")
            second = run_gps_pipeline(inp, metadata, root / "second", 120.0)
            self.assertEqual(first, second)
            self.assertEqual(inp.read_bytes(), raw)
            self.assertEqual(first["derived_kind"], "DERIVED")
            self.assertTrue(all(value is None for value in first["model_results"].values()))
            with self.assertRaises(GPSInputError):
                run_gps_pipeline(inp, metadata, root / "first")
            with self.assertRaises(GPSInputError):
                run_gps_pipeline(inp, metadata, root)

    def test_failure_has_quality_report_without_success_csv(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            raw, meta = fixture([{"vehicle_id": "", "timestamp": "x", "longitude": "x", "latitude": "x"}])
            (root / "input.csv").write_bytes(raw)
            (root / "metadata.json").write_text(json.dumps(meta))
            with self.assertRaises(GPSInputError):
                run_gps_pipeline(root / "input.csv", root / "metadata.json", root / "output")
            self.assertEqual(json.loads((root / "output/quality_report.json").read_text())["status"], "failed")
            self.assertFalse((root / "output/validated_positions.csv").exists())

    def test_scenario_is_seeded_and_explicitly_synthetic(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            boundary = ROOT / "public/data/seoul-districts-2013.geojson"
            first = generate(boundary, root / "a", 42)
            second = generate(boundary, root / "b", 42)
            self.assertEqual(first, second)
            self.assertEqual(first["generator"]["observations"], 72)
            self.assertFalse(first["generator"]["road_constrained"])
            run = run_gps_pipeline(root / "a/mapo_synthetic_gps.csv", root / "a/mapo_synthetic_gps.metadata.json", root / "validated")
            self.assertEqual(run["source_kind"], "SYNTHETIC")

    def test_strict_json_and_malformed_source_types_publish_failure_only(self):
        raw, meta = fixture()
        variants = [
            json.dumps(meta)[:-1] + ', "schema_version": "1.0"}',
            json.dumps(meta)[:-1] + ', "unused": NaN}',
            json.dumps(meta)[:-1] + ', "unused": Infinity}',
        ]
        for bad_kind in ([], {}, 123, None):
            candidate = copy.deepcopy(meta)
            candidate["source"]["kind"] = bad_kind
            variants.append(json.dumps(candidate))
        for variant in variants:
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                (root / "input.csv").write_bytes(raw)
                (root / "metadata.json").write_text(variant)
                with self.assertRaises(GPSInputError):
                    run_gps_pipeline(root / "input.csv", root / "metadata.json", root / "output")
                self.assertEqual(sorted(p.name for p in (root / "output").iterdir()), ["processing_log.jsonl", "quality_report.json"])
                self.assertEqual(json.loads((root / "output/quality_report.json").read_text())["status"], "failed")

    def test_late_export_fault_cleans_partial_outputs_and_stage(self):
        for fault in ("csv", "manifest"):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                raw, meta = fixture()
                (root / "input.csv").write_bytes(raw)
                (root / "metadata.json").write_text(json.dumps(meta))

                def csv_fault(writer, rows):
                    writer.writerow(rows[0])
                    raise OSError("simulated CSV disk failure")

                original_write = gps_input._write_json

                def manifest_fault(path, value):
                    if Path(path).name == "run_manifest.json":
                        Path(path).write_text("partial manifest")
                        raise OSError("simulated manifest disk failure")
                    return original_write(path, value)

                target = "pipeline.gps_input.csv.DictWriter.writerows" if fault == "csv" else "pipeline.gps_input._write_json"
                with patch(target, new=csv_fault if fault == "csv" else manifest_fault):
                    with self.assertRaisesRegex(GPSInputError, "simulated"):
                        run_gps_pipeline(root / "input.csv", root / "metadata.json", root / "output")
                self.assertEqual(sorted(p.name for p in (root / "output").iterdir()), ["processing_log.jsonl", "quality_report.json"])
                self.assertEqual(json.loads((root / "output/quality_report.json").read_text())["status"], "failed")
                self.assertEqual(list(root.glob(".atlas-gps-*")), [])
                self.assertEqual((root / "input.csv").read_bytes(), raw)

    def test_cli_input_missing_and_output_file_return_two_without_traceback(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            raw, meta = fixture()
            (root / "input.csv").write_bytes(raw)
            (root / "metadata.json").write_text(json.dumps(meta))
            (root / "output-file").write_text("preserve existing content")
            cases = [
                (root / "absent.csv", root / "output-missing"),
                (root / "input.csv", root / "output-file"),
            ]
            for source, output in cases:
                stderr = io.StringIO()
                with redirect_stderr(stderr):
                    status = main(["--input", str(source), "--metadata", str(root / "metadata.json"), "--output", str(output)])
                self.assertEqual(status, 2)
                self.assertNotIn("Traceback", stderr.getvalue())
                self.assertTrue(stderr.getvalue().strip())
            self.assertEqual((root / "output-file").read_text(), "preserve existing content")
            self.assertEqual(json.loads((root / "output-missing/quality_report.json").read_text())["status"], "failed")


if __name__ == "__main__":
    unittest.main()
